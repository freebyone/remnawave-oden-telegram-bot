"""Referral withdrawal via support, and the main-menu «Подарить другу» entry."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest


ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.config import Settings, settings
from app.handlers.subscription import gift
from app.keyboards.inline import get_referral_keyboard


def _buttons(markup):
    return [button for row in markup.inline_keyboard for button in row]


def test_withdraw_links_to_support_when_in_bot_withdrawal_is_off(monkeypatch) -> None:
    monkeypatch.setattr(Settings, 'is_referral_withdrawal_enabled', lambda self: False)
    monkeypatch.setattr(settings, 'SUPPORT_USERNAME', '@oden_vpn_support')

    buttons = _buttons(get_referral_keyboard('ru'))

    assert 'https://t.me/oden_vpn_support' in [button.url for button in buttons]
    assert 'referral_withdrawal' not in [button.callback_data for button in buttons]


def test_in_bot_withdrawal_replaces_support_link(monkeypatch) -> None:
    """Never two withdrawal buttons: if the admin enabled in-bot requests, they win."""
    monkeypatch.setattr(Settings, 'is_referral_withdrawal_enabled', lambda self: True)
    monkeypatch.setattr(settings, 'SUPPORT_USERNAME', '@oden_vpn_support')

    buttons = _buttons(get_referral_keyboard('ru'))

    assert 'referral_withdrawal' in [button.callback_data for button in buttons]
    assert 'https://t.me/oden_vpn_support' not in [button.url for button in buttons]


def test_referral_screen_keeps_its_original_actions(monkeypatch) -> None:
    monkeypatch.setattr(settings, 'SUPPORT_USERNAME', '@oden_vpn_support')

    callbacks = [button.callback_data for button in _buttons(get_referral_keyboard('ru'))]

    for action in ('referral_create_invite', 'referral_show_qr', 'referral_list', 'referral_analytics'):
        assert action in callbacks
    assert callbacks[-1] == 'back_to_menu'


@pytest.mark.anyio('asyncio')
async def test_gift_cancel_from_main_menu_returns_to_main_menu(monkeypatch) -> None:
    monkeypatch.setattr(gift.user_cart_service, 'get_user_cart', AsyncMock(return_value=None))
    back_to_menu = AsyncMock()
    monkeypatch.setattr('app.handlers.menu.handle_back_to_menu', back_to_menu)
    subscription_info = AsyncMock()
    monkeypatch.setattr(gift, 'show_subscription_info', subscription_info)

    state = SimpleNamespace(
        get_data=AsyncMock(return_value={'gift_origin_callback': 'gift_from_menu'}),
        clear=AsyncMock(),
    )
    callback = SimpleNamespace(message=SimpleNamespace(), answer=AsyncMock())
    db_user = SimpleNamespace(id=1, language='ru')
    db = SimpleNamespace()

    await gift.handle_gift_cancel(callback, db_user, db, state)

    back_to_menu.assert_awaited_once_with(callback, state, db_user, db)
    subscription_info.assert_not_awaited()
