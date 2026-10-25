"""Oden: баннер раздела вместо логотипа на экранах «Оплата», «Подключение», «Подарок».

Хендлер раздела включает баннер на время своей работы (``with screen_banner('buy')``),
а патч Message.edit_text/answer (message_patch) берёт фото баннера вместо логотипа.
Остальные экраны по-прежнему с логотипом. Файл не найден — обычный логотип.
"""

from __future__ import annotations

import functools
import inspect
from collections.abc import Awaitable, Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from typing import Any

from aiogram.types import FSInputFile, Message


BANNERS_DIR = Path(__file__).resolve().parent.parent / 'assets' / 'banners'

_current: ContextVar[str | None] = ContextVar('oden_screen_banner', default=None)
# file_id после первой отправки — дальше Telegram не перекачивает картинку.
_file_ids: dict[str, str] = {}


@contextmanager
def screen_banner(name: str) -> Iterator[None]:
    token = _current.set(name)
    try:
        yield
    finally:
        _current.reset(token)


def with_banner(name: str, handler: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
    """Обёртка хендлера: экран рисуется с баннером ``name``.

    aiogram с **kwargs у обёртки передал бы все данные апдейта — отдаём хендлеру
    только те, что он объявил.
    """
    params = inspect.signature(handler).parameters
    accepts_any = any(p.kind is inspect.Parameter.VAR_KEYWORD for p in params.values())

    @functools.wraps(handler)
    async def wrapped(event: Any, **data: Any) -> Any:
        kwargs = data if accepts_any else {key: value for key, value in data.items() if key in params}
        with screen_banner(name):
            return await handler(event, **kwargs)

    # aiogram смотрит на сигнатуру вызываемого: у обёртки — «всё через **data».
    wrapped.__signature__ = inspect.Signature(  # type: ignore[attr-defined]
        [
            inspect.Parameter('event', inspect.Parameter.POSITIONAL_OR_KEYWORD),
            inspect.Parameter('data', inspect.Parameter.VAR_KEYWORD),
        ]
    )
    del wrapped.__wrapped__
    return wrapped


# Какой баннер у экрана, открытого кнопкой: (точное значение или префикс callback_data, баннер).
# Первое совпадение выигрывает. Экран вне списка — с обычным логотипом.
_CALLBACK_BANNERS: tuple[tuple[str, str], ...] = (
    # Продление
    ('se:', 'renew'),
    ('subscription_extend', 'renew'),
    ('extend_period', 'renew'),
    ('tariff_extend', 'renew'),
    # Редактирование подписки: карточка, устройства, автоплатёж
    ('buy_edit', 'edit'),
    ('sm:', 'edit'),
    ('sd:', 'edit'),
    ('change_devices', 'edit'),
    ('device_management', 'edit'),
    ('subscription_autopay', 'edit'),
    ('autopay_', 'edit'),
    ('my_subscriptions', 'edit'),
    ('menu_subscription', 'edit'),
    # Реферальная программа и подарок
    ('oden_referral', 'partner'),
    ('gift_', 'gift'),
    ('subscription_gift', 'gift'),
    # Подключение
    ('subscription_connect', 'connect'),
    ('device_guide_', 'connect'),
    ('app_list_', 'connect'),
    ('app_', 'connect'),
    # Оплата и смена тарифа
    ('menu_buy', 'buy'),
    ('buy_change', 'buy'),
    ('tariff_', 'buy'),
    ('buy_subscription_tariffs', 'buy'),
    ('subscription_upgrade', 'buy'),
    ('subscription_purchase', 'buy'),
)


def banner_for_callback(data: str | None) -> str | None:
    if not data:
        return None
    for prefix, name in _CALLBACK_BANNERS:
        if data == prefix or data.startswith(prefix):
            return name
    return None


class ScreenBannerMiddleware:
    """Включает баннер раздела на время обработки нажатия кнопки этого раздела.

    Так баннер остаётся и на экранах, куда возвращают «Назад» / «Отмена», а не
    только у первого экрана раздела.
    """

    async def __call__(self, handler, event, data):
        name = banner_for_callback(getattr(event, 'data', None))
        if not name:
            return await handler(event, data)
        with screen_banner(name):
            return await handler(event, data)


def current_banner_media() -> str | FSInputFile | None:
    """file_id или файл баннера текущего экрана; None — баннера нет."""
    name = _current.get()
    if not name:
        return None
    if name in _file_ids:
        return _file_ids[name]
    path = BANNERS_DIR / f'{name}.png'
    return FSInputFile(path) if path.is_file() else None


def remember_banner_file_id(result: Message | None) -> None:
    name = _current.get()
    if name and name not in _file_ids and result is not None and getattr(result, 'photo', None):
        _file_ids[name] = result.photo[-1].file_id
