"""Навигация «Назад» в покупке и в «Подключить VPN».

1. Покупка → срок → способ оплаты → окно оплаты → «Назад» → «Назад» вела в
   профиль: «Назад» провайдеров шлют balance_topup / menu_balance, а счёт
   Platega/CryptoBot/Stars ещё и чистит FSM. Теперь экран покупки запоминает
   себя (Redis, 30 мин), и оба обработчика возвращают на него.
2. Инструкция по устройству: «К подписке» вела в главное меню; теперь одна
   «Назад» — на выбор устройства («Подключить VPN»).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

import app.handlers.subscription.purchase_return as pr
from app.config import settings
from app.keyboards.inline import get_app_selection_keyboard, get_connection_guide_keyboard


class FakeRedis:
    def __init__(self) -> None:
        self.store: dict[str, str] = {}
        self.ttl: dict[str, int] = {}

    async def setex(self, key, ttl, value):
        self.store[key] = value
        self.ttl[key] = ttl

    async def get(self, key):
        return self.store.get(key)

    async def delete(self, key):
        self.store.pop(key, None)


@pytest.fixture
def fake_redis(monkeypatch: pytest.MonkeyPatch) -> FakeRedis:
    redis = FakeRedis()
    monkeypatch.setattr(pr, '_client', redis)
    return redis


async def test_remember_and_forget(fake_redis: FakeRedis) -> None:
    await pr.remember_purchase_screen(7, 'tariff_period:5:90')
    assert await pr.pending_purchase_screen(7) == 'tariff_period:5:90'
    assert fake_redis.ttl['purchase_return:7'] == pr.TTL_SECONDS
    assert await pr.pending_purchase_screen(8) is None

    await pr.forget_purchase_screen(7)
    assert await pr.pending_purchase_screen(7) is None


async def test_only_purchase_screens_are_remembered(fake_redis: FakeRedis) -> None:
    await pr.remember_purchase_screen(7, 'menu_buy')
    await pr.remember_purchase_screen(7, None)
    assert fake_redis.store == {}


async def test_return_to_purchase_redraws_period_screen(
    fake_redis: FakeRedis, monkeypatch: pytest.MonkeyPatch
) -> None:
    period = AsyncMock()
    extend = AsyncMock()
    monkeypatch.setattr(pr, '_screens', {'tariff_period:': period, 'tariff_extend:': extend})

    callback = MagicMock()
    callback.model_copy = lambda update: MagicMock(data=update['data'])
    user = MagicMock(id=7)

    assert await pr.return_to_purchase(callback, user, None, None) is False

    await pr.remember_purchase_screen(7, 'tariff_period:5:90')
    assert await pr.return_to_purchase(callback, user, None, None) is True
    assert period.await_args.args[0].data == 'tariff_period:5:90'

    await pr.remember_purchase_screen(7, 'tariff_extend:1:5:90')
    assert await pr.return_to_purchase(callback, user, None, None) is True
    assert extend.await_args.args[0].data == 'tariff_extend:1:5:90'


def test_purchase_module_registers_its_screens() -> None:
    from aiogram import Dispatcher

    from app.handlers.subscription import tariff_purchase

    tariff_purchase.register_tariff_purchase_handlers(Dispatcher())
    assert pr._screens['tariff_period:'] is tariff_purchase.select_tariff_period
    assert pr._screens['tariff_extend:'] is tariff_purchase.select_tariff_extend_period


def _callbacks(kb) -> list[str]:
    return [btn.callback_data for row in kb.inline_keyboard for btn in row if btn.callback_data]


@pytest.mark.parametrize('multi', [False, True])
def test_guide_back_goes_to_device_picker(monkeypatch: pytest.MonkeyPatch, multi: bool) -> None:
    monkeypatch.setattr(settings, 'MULTI_TARIFF_ENABLED', multi, raising=False)
    monkeypatch.setattr(settings, 'SALES_MODE', 'tariffs', raising=False)
    app = {'name': 'Happ', 'blocks': []}
    kb = get_connection_guide_keyboard('https://sub.example/x', app, 'ios', 'ru', sub_id=3)
    cbs = _callbacks(kb)
    expected = 'subscription_connect:3' if multi else 'subscription_connect'
    assert cbs[-1] == expected
    assert 'back_to_menu' not in cbs
    assert 'menu_subscription' not in cbs
    # одна кнопка «назад», без дубля «Выбрать другое устройство»
    assert sum(cb.startswith('subscription_connect') for cb in cbs) == 1


def test_other_apps_back_goes_to_device_guide() -> None:
    kb = get_app_selection_keyboard('android', [{'name': 'Incy', 'id': 'incy'}], 'ru')
    assert _callbacks(kb)[-1] == 'device_guide_android'
    assert 'menu_subscription' not in _callbacks(kb)
