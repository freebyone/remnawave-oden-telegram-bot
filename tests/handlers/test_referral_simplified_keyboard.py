"""The referral screen is reduced to two actions, opened from «Мой профиль».

- «📤 Отправить приглашение»: a t.me/share/url link, so Telegram opens its
  chat picker with the user's referral link prefilled.
- «💸 Вывод средств»: a link to the support account (SUPPORT_USERNAME), not an
  in-bot withdrawal request.
- Back returns to the profile, where the screen is opened from.
"""

from __future__ import annotations

import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.config import settings
from app.keyboards.inline import get_referral_keyboard


SHARE_URL = 'https://t.me/share/url?url=https%3A%2F%2Ft.me%2Foden_vpn_bot%3Fstart%3Dabc&text=hi'


def _buttons(markup):
    return [button for row in markup.inline_keyboard for button in row]


def test_invite_and_withdraw_are_links(monkeypatch) -> None:
    monkeypatch.setattr(settings, 'SUPPORT_USERNAME', '@oden_vpn_support')

    buttons = _buttons(get_referral_keyboard('ru', invite_share_url=SHARE_URL))
    urls = [button.url for button in buttons if button.url]

    assert SHARE_URL in urls
    assert 'https://t.me/oden_vpn_support' in urls


def test_old_actions_are_gone_and_back_goes_to_profile(monkeypatch) -> None:
    monkeypatch.setattr(settings, 'SUPPORT_USERNAME', '@oden_vpn_support')

    callbacks = [button.callback_data for button in _buttons(get_referral_keyboard('ru', invite_share_url=SHARE_URL))]

    for removed in ('referral_create_invite', 'referral_show_qr', 'referral_list', 'referral_analytics'):
        assert removed not in callbacks
    assert callbacks[-1] == 'menu_my_profile'


def test_no_invite_button_without_link(monkeypatch) -> None:
    monkeypatch.setattr(settings, 'SUPPORT_USERNAME', '@oden_vpn_support')

    buttons = _buttons(get_referral_keyboard('ru'))

    assert not any(button.url and 't.me/share/url' in button.url for button in buttons)
