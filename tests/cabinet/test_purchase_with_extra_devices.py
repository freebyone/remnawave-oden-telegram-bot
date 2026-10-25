"""Oden: число устройств выбирается прямо при покупке тарифа в кабинете.

Кабинет шлёт ``device_limit`` (входящие в тариф + докупленные). Цена — тем же
расчётом, что продление с докупленными устройствами (pricing_engine), лимит
подписки — выбранный. Докупка выключена, когда цена устройства у тарифа 0, и
ограничена максимумом устройств тарифа.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.cabinet.schemas.subscription import TariffPurchaseRequest
from app.config import settings
from app.database.models import Base, Subscription, Tariff, User
from app.services.pricing_engine import extra_device_terms, validate_chosen_device_limit
from tests.fixtures.sqlite_memory import memory_session


TABLES = list(Base.metadata.sorted_tables)


class _FakePanelSync:
    async def update_remnawave_user(self, db, subscription, **kwargs):
        return SimpleNamespace(id=9001, used_traffic_bytes=0)

    async def create_remnawave_user(self, db, subscription, **kwargs):
        return SimpleNamespace(id=9001, used_traffic_bytes=0)

    async def enable_remnawave_user(self, panel_user_id, db=None):
        return True


@pytest.fixture(autouse=True)
def tariffs_mode(monkeypatch):
    monkeypatch.setattr(settings, 'SALES_MODE', 'tariffs')
    monkeypatch.setattr(settings, 'MULTI_TARIFF_ENABLED', True)
    monkeypatch.setattr(settings, 'PRICE_PER_DEVICE', 5000)
    monkeypatch.setattr(settings, 'MAX_DEVICES_LIMIT', 10)


@pytest.fixture
def panel(monkeypatch) -> _FakePanelSync:
    import app.services.subscription_renewal_service as renewal_module
    import app.services.subscription_service as subscription_service_module

    monkeypatch.setattr(subscription_service_module, 'SubscriptionService', _FakePanelSync)
    monkeypatch.setattr(renewal_module, 'SubscriptionService', _FakePanelSync)
    return _FakePanelSync()


def _tariff(*, device_price: int | None = 10000, max_devices: int | None = 6) -> Tariff:
    return Tariff(
        id=1,
        name='Индивидуальная',
        description='',
        is_active=True,
        is_daily=False,
        period_prices={'30': 29000, '90': 69000},
        traffic_limit_gb=0,
        device_limit=3,
        device_price_kopeks=device_price,
        max_device_limit=max_devices,
        allowed_squads=['squad-1'],
        display_order=1,
    )


# ── Правила выбора ─────────────────────────────────────────────────────────


def test_terms_follow_tariff_price_then_settings() -> None:
    assert extra_device_terms(_tariff(device_price=10000, max_devices=6)) == (10000, 6)
    # Цена у тарифа не задана — как докупка в кабинете: PRICE_PER_DEVICE и MAX_DEVICES_LIMIT.
    assert extra_device_terms(_tariff(device_price=None, max_devices=6)) == (5000, 10)


def test_validate_chosen_device_limit() -> None:
    tariff = _tariff(device_price=10000, max_devices=6)
    assert validate_chosen_device_limit(tariff, 3) is None
    assert validate_chosen_device_limit(tariff, 5) is None
    assert validate_chosen_device_limit(tariff, 2) is not None  # меньше, чем в тарифе
    assert validate_chosen_device_limit(tariff, 7) is not None  # больше максимума
    # Цена устройства 0 — докупка выключена, но лимит тарифа взять можно.
    free_devices = _tariff(device_price=0)
    assert validate_chosen_device_limit(free_devices, 3) is None
    assert validate_chosen_device_limit(free_devices, 4) is not None


# ── Покупка ────────────────────────────────────────────────────────────────


async def _purchase(db, tariff: Tariff, *, device_limit: int | None, balance: int = 1_000_000):
    from app.cabinet.routes.subscription_modules.purchase import purchase_tariff

    db.add_all(
        [
            User(id=1, telegram_id=1001, first_name='U', language='ru', status='active', balance_kopeks=balance),
            tariff,
        ]
    )
    await db.commit()
    user = await db.get(User, 1)
    request = TariffPurchaseRequest(tariff_id=1, period_days=90, device_limit=device_limit)
    return await purchase_tariff(request=request, user=user, db=db)


@pytest.mark.asyncio
async def test_extra_devices_are_charged_and_applied(monkeypatch, panel):
    async with memory_session(monkeypatch, TABLES) as db:
        response = await _purchase(db, _tariff(), device_limit=5)

        assert response.get('success') is True, response
        # 690 ₽ за 3 месяца + 2 устройства × 100 ₽ × 3 месяца.
        assert response['charged_amount'] == 69000 + 2 * 10000 * 3
        subscription = await db.get(Subscription, 1)
        assert subscription.device_limit == 5


@pytest.mark.asyncio
async def test_without_choice_tariff_limit_is_kept(monkeypatch, panel):
    async with memory_session(monkeypatch, TABLES) as db:
        response = await _purchase(db, _tariff(), device_limit=None)

        assert response['charged_amount'] == 69000
        assert (await db.get(Subscription, 1)).device_limit == 3


@pytest.mark.asyncio
async def test_extra_devices_rejected_when_tariff_price_is_zero(monkeypatch, panel):
    async with memory_session(monkeypatch, TABLES) as db:
        with pytest.raises(HTTPException) as exc:
            await _purchase(db, _tariff(device_price=0), device_limit=4)
        assert exc.value.status_code == 400
        # Ни списания, ни подписки.
        assert (await db.get(User, 1)).balance_kopeks == 1_000_000
        assert await db.get(Subscription, 1) is None


@pytest.mark.asyncio
async def test_extra_devices_rejected_above_max(monkeypatch, panel):
    async with memory_session(monkeypatch, TABLES) as db:
        with pytest.raises(HTTPException) as exc:
            await _purchase(db, _tariff(max_devices=4), device_limit=5)
        assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_insufficient_balance_cart_remembers_chosen_devices(monkeypatch, panel):
    from app.services import user_cart_service as cart_module

    saved: dict = {}

    async def _save(user_id, cart_data):
        saved.update(cart_data)
        return True

    monkeypatch.setattr(cart_module.user_cart_service, 'save_user_cart', _save)

    async with memory_session(monkeypatch, TABLES) as db:
        with pytest.raises(HTTPException) as exc:
            await _purchase(db, _tariff(), device_limit=5, balance=0)

    assert exc.value.status_code == 402
    assert saved['chosen_device_limit'] == 5
    assert saved['total_price'] == 69000 + 2 * 10000 * 3
