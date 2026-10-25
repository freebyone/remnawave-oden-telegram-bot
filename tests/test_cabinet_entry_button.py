"""«Личный кабинет» в главном меню открывает мини-приложение, а остальные
кнопки остаются в боте.

Адрес кабинета берётся из MENU_BUTTON_WEBAPP_URL (кнопка меню чата), когда
MINIAPP_CUSTOM_URL пуст: тот превратил бы в ссылки на кабинет все кнопки бота,
а Oden ведёт пользователя в кабинет только по его выбору.
"""

from __future__ import annotations

import pytest

from app.config import settings
from app.keyboards.inline import get_main_menu_keyboard


CABINET = 'https://app.example.test'


@pytest.fixture
def cabinet_menu(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, 'MAIN_MENU_MODE', 'cabinet', raising=False)
    monkeypatch.setattr(settings, 'MINIAPP_CUSTOM_URL', '', raising=False)
    monkeypatch.setattr(settings, 'MENU_BUTTON_WEBAPP_URL', '', raising=False)

    import app.utils.button_styles_cache as styles_cache
    import app.utils.menu_layout_cache as layout_cache

    monkeypatch.setattr(layout_cache, '_cached_layout', None, raising=False)
    monkeypatch.setattr(styles_cache, '_cached_styles', None, raising=False)
    return monkeypatch


def _flat(kb):
    return [btn for row in kb.inline_keyboard for btn in row]


def test_no_cabinet_address_no_button(cabinet_menu) -> None:
    buttons = _flat(get_main_menu_keyboard(language='ru', is_admin=False))
    assert all(btn.web_app is None for btn in buttons)


def test_cabinet_button_from_menu_button_url(cabinet_menu) -> None:
    cabinet_menu.setattr(settings, 'MENU_BUTTON_WEBAPP_URL', CABINET, raising=False)

    kb = get_main_menu_keyboard(language='ru', is_admin=False)
    # «Личный кабинет» — последней строкой (для не-админа), серая.
    last_row = kb.inline_keyboard[-1]

    assert len(last_row) == 1
    assert last_row[0].web_app is not None
    assert last_row[0].web_app.url == CABINET
    assert last_row[0].style is None

    # Всё остальное меню — обычные кнопки бота, без перехода в кабинет.
    others = _flat(kb)[:-1]
    assert others, 'menu must keep its regular buttons'
    assert all(btn.web_app is None and btn.callback_data for btn in others)


def test_miniapp_custom_url_still_wins_for_cabinet_button(cabinet_menu) -> None:
    cabinet_menu.setattr(settings, 'MINIAPP_CUSTOM_URL', 'https://custom.example.test/', raising=False)
    cabinet_menu.setattr(settings, 'MENU_BUTTON_WEBAPP_URL', CABINET, raising=False)

    kb = get_main_menu_keyboard(language='ru', is_admin=False)
    assert kb.inline_keyboard[-1][0].web_app.url == 'https://custom.example.test'
