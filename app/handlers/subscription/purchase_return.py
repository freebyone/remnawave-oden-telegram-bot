"""«Назад» из оплаты возвращает к покупке подписки, а не в профиль.

Экран «Недостаточно средств» при покупке/продлении показывает способы оплаты
недостающей суммы. Дальше у каждого платёжного провайдера своя «Назад» — на
общее пополнение (``balance_topup``) или на баланс (``menu_balance``, который
ведёт в профиль). Человек, нажимая «Назад» из окна оплаты, ждёт вернуться к
выбору срока, а попадал в профиль.

Поэтому экран покупки запоминает себя, а обработчики ``balance_topup`` и
``menu_balance`` в течение ``TTL_SECONDS`` возвращают туда. Метка лежит в Redis,
а не в FSM: экраны счёта провайдеров (Platega, CryptoBot, Stars) в конце делают
``state.clear()``. Профиль и главное меню метку стирают — обычное пополнение из
профиля работает как раньше. Нет Redis — всё работает по-старому.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

import structlog
from aiogram import types

from app.utils.redis_client import create_redis


logger = structlog.get_logger(__name__)

TTL_SECONDS = 30 * 60
_KEY = 'purchase_return:{user_id}'

# Экраны, на которые умеем вернуться (callback_data, который их рисует).
_SUPPORTED_PREFIXES = ('tariff_period:', 'tariff_extend:')

# Обработчики экранов регистрирует сам tariff_purchase (register_purchase_screen):
# импорт отсюда в tariff_purchase замкнул бы кольцо меню → покупка → платежи.
_screens: dict[str, Callable[..., Awaitable[Any]]] = {}

_client = None


def register_purchase_screen(prefix: str, handler: Callable[..., Awaitable[Any]]) -> None:
    _screens[prefix] = handler


def _redis():
    global _client
    if _client is None:
        try:
            _client = create_redis()
        except Exception as error:  # pragma: no cover - нет Redis
            logger.warning('purchase_return: Redis недоступен', error=error)
            return None
    return _client


def is_supported(callback_data: str | None) -> bool:
    return bool(callback_data) and str(callback_data).startswith(_SUPPORTED_PREFIXES)


async def remember_purchase_screen(user_id: int, callback_data: str | None) -> None:
    if not is_supported(callback_data):
        return
    client = _redis()
    if client is None:
        return
    try:
        await client.setex(_KEY.format(user_id=user_id), TTL_SECONDS, str(callback_data))
    except Exception as error:
        logger.warning('purchase_return: не удалось запомнить экран покупки', error=error)


async def forget_purchase_screen(user_id: int) -> None:
    client = _redis()
    if client is None:
        return
    try:
        await client.delete(_KEY.format(user_id=user_id))
    except Exception as error:
        logger.warning('purchase_return: не удалось стереть метку', error=error)


async def pending_purchase_screen(user_id: int) -> str | None:
    """callback_data экрана покупки, если человек ушёл с него в оплату недавно."""
    client = _redis()
    if client is None:
        return None
    try:
        value = await client.get(_KEY.format(user_id=user_id))
    except Exception as error:
        logger.warning('purchase_return: не удалось прочитать метку', error=error)
        return None
    if isinstance(value, bytes):
        value = value.decode()
    return value if is_supported(value) else None


async def return_to_purchase(callback: types.CallbackQuery, db_user, db, state) -> bool:
    """Перерисовать экран покупки вместо пополнения/профиля. True — если вернули."""
    target = await pending_purchase_screen(db_user.id)
    if not target:
        return False
    handler = next((h for prefix, h in _screens.items() if target.startswith(prefix)), None)
    if handler is None:
        return False

    redirected = callback.model_copy(update={'data': target})
    await handler(redirected, db_user, db, state)
    return True
