"""«Мой профиль» is the single home for balance actions.

Regression: the standalone balance screen (menu_balance) offered «Пополнить»,
and every payment provider's «Назад» led back to menu_balance — so
«Пополнить» → «Назад» → «Пополнить» looped. Balance top-up and history now
live in the profile, and menu_balance hands off there.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest


ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.config import Settings
from app.handlers import menu
from app.handlers.balance.main import show_balance_menu


def _callbacks(keyboard) -> list[str]:
    return [button.callback_data for row in keyboard.inline_keyboard for button in row]


@pytest.mark.anyio('asyncio')
async def test_balance_menu_opens_main_menu(monkeypatch: pytest.MonkeyPatch) -> None:
    """Профиля в меню бота нет (25.10.2026, он в кабинете): menu_balance —
    куда ведут «Назад» провайдеров — открывает главное меню."""
    main_menu = AsyncMock()
    monkeypatch.setattr('app.handlers.menu.handle_back_to_menu', main_menu)
    monkeypatch.setattr(
        'app.handlers.subscription.purchase_return.return_to_purchase', AsyncMock(return_value=False)
    )

    callback = SimpleNamespace(message=SimpleNamespace(), answer=AsyncMock())
    db_user = SimpleNamespace(id=1, language='ru')
    db = SimpleNamespace()
    state = SimpleNamespace(update_data=AsyncMock())

    await show_balance_menu(callback, db_user, db, state)

    main_menu.assert_awaited_once_with(callback, state, db_user, db)


@pytest.mark.anyio('asyncio')
async def test_profile_has_balance_actions_without_loop(monkeypatch: pytest.MonkeyPatch) -> None:
    # Keep the subscription section out of the way: it needs a database.
    monkeypatch.setattr(Settings, 'is_multi_tariff_enabled', lambda self: False)
    render = AsyncMock()
    monkeypatch.setattr(menu, 'edit_or_answer_photo', render)

    db_user = SimpleNamespace(
        id=1,
        telegram_id=1,
        first_name='Тест',
        username=None,
        created_at=None,
        balance_kopeks=0,
        language='ru',
    )
    callback = SimpleNamespace(answer=AsyncMock())

    await menu.show_my_profile(callback, db_user, SimpleNamespace())

    callbacks = _callbacks(render.call_args.kwargs['keyboard'])
    assert 'balance_topup' in callbacks
    assert 'balance_history' in callbacks
    # The profile must not send the user to the old balance screen — that
    # screen's own «Пополнить» is what made the loop.
    assert 'menu_balance' not in callbacks
    assert callbacks[-1] == 'back_to_menu'
