"""Regression test: cabinet-mode main menu exposes the user-facing buttons of
the simplified /start screen — Оплатить подписку, Подключить VPN, Пробный
период, Подарить другу — each on its own row, each keeping its Bot API 9.4
color even though the external cabinet web app is disabled
(MINIAPP_CUSTOM_URL empty). «Мой профиль» и «Реферальная система» живут в
кабинете (25.10.2026) и в меню бота не показываются.
"""

from __future__ import annotations

import pytest

from app.config import settings
from app.keyboards.inline import get_main_menu_keyboard


EXPECTED_CALLBACKS = [
    'menu_buy',
    'subscription_connect',
    'menu_trial',
    'gift_from_menu',
]

MOVED_TO_CABINET = ['menu_my_profile', 'menu_referrals']


@pytest.fixture
def cabinet_mode_no_url(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, 'MAIN_MENU_MODE', 'cabinet', raising=False)
    monkeypatch.setattr(settings, 'MINIAPP_CUSTOM_URL', '', raising=False)

    # Both the layout and the per-section style are process-wide module caches
    # (populated from DB at bot startup). Force them back to defaults so this
    # test is deterministic regardless of what ran before it in the same
    # pytest session.
    import app.utils.button_styles_cache as styles_cache
    import app.utils.menu_layout_cache as layout_cache

    monkeypatch.setattr(layout_cache, '_cached_layout', None, raising=False)
    monkeypatch.setattr(styles_cache, '_cached_styles', None, raising=False)
    return monkeypatch


def test_main_menu_has_six_buttons_one_per_row(cabinet_mode_no_url) -> None:
    kb = get_main_menu_keyboard(language='ru', is_admin=False)

    rows_with_buttons = [row for row in kb.inline_keyboard if row]
    callbacks_per_row = [[btn.callback_data for btn in row] for row in rows_with_buttons]

    for expected in EXPECTED_CALLBACKS:
        assert any(expected in row for row in callbacks_per_row), (
            f'Expected callback {expected!r} missing from main menu rows: {callbacks_per_row}'
        )

    for expected in EXPECTED_CALLBACKS:
        matching_rows = [row for row in callbacks_per_row if expected in row]
        assert len(matching_rows[0]) == 1, (
            f'{expected!r} must be alone on its row (one button per row), got {matching_rows[0]}'
        )


# 25.10.2026: красные — только «Оплатить подписку» и «Пробный период», остальные серые.
RED_CALLBACKS = {'menu_buy', 'menu_trial'}


def test_main_menu_button_colors_without_cabinet_url(cabinet_mode_no_url) -> None:
    kb = get_main_menu_keyboard(language='ru', is_admin=False)

    flat_buttons = [btn for row in kb.inline_keyboard for btn in row]
    by_callback = {btn.callback_data: btn for btn in flat_buttons}

    for expected in EXPECTED_CALLBACKS:
        button = by_callback[expected]
        assert button.web_app is None, f'{expected!r} must not force the user into the disabled web cabinet'
        if expected in RED_CALLBACKS:
            assert button.style == 'danger', f'{expected!r} must stay red'
        else:
            assert button.style is None, f'{expected!r} must be grey (no color)'


def test_profile_and_referral_are_not_in_the_bot_menu(cabinet_mode_no_url) -> None:
    kb = get_main_menu_keyboard(language='ru', is_admin=False)
    flat_callbacks = [btn.callback_data for row in kb.inline_keyboard for btn in row]
    for moved in MOVED_TO_CABINET:
        assert moved not in flat_callbacks, f'{moved!r} moved to the cabinet'


def test_admin_row_still_present_for_admins(cabinet_mode_no_url) -> None:
    kb = get_main_menu_keyboard(language='ru', is_admin=True)

    flat_callbacks = [btn.callback_data for row in kb.inline_keyboard for btn in row]
    assert 'admin_panel' in flat_callbacks
