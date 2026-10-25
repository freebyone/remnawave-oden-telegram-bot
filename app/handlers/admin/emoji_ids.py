"""Админ присылает боту анимированные (custom) эмодзи — бот отвечает их ID.

ID нужны для ``icon_custom_emoji_id`` кнопок главного меню (стили кнопок,
``CABINET_BUTTON_STYLES``): Telegram рисует такой эмодзи иконкой на кнопке, если
у владельца бота Telegram Premium. Узнать ID из приложения нельзя — отсюда этот
помощник. Срабатывает только у админов, только в личке, только вне диалогов
(FSM) и только если в сообщении есть custom emoji, поэтому ничего не перехватывает.
"""

from __future__ import annotations

import html

from aiogram import Dispatcher, F, types
from aiogram.filters import StateFilter

from app.config import settings


def custom_emoji_ids(message: types.Message) -> list[tuple[str, str]]:
    """Пары (эмодзи как в тексте, custom_emoji_id) в порядке появления, без повторов."""
    text = message.text or message.caption or ''
    entities = message.entities or message.caption_entities or []
    found: list[tuple[str, str]] = []
    seen: set[str] = set()
    for entity in entities:
        if entity.type != 'custom_emoji' or not entity.custom_emoji_id:
            continue
        if entity.custom_emoji_id in seen:
            continue
        seen.add(entity.custom_emoji_id)
        found.append((entity.extract_from(text), entity.custom_emoji_id))
    return found


def _has_custom_emoji(message: types.Message) -> bool:
    return bool(custom_emoji_ids(message))


def _is_admin(message: types.Message) -> bool:
    return bool(message.from_user) and settings.is_admin(message.from_user.id)


async def reply_custom_emoji_ids(message: types.Message) -> None:
    pairs = custom_emoji_ids(message)
    lines = ['🆔 <b>ID анимированных эмодзи</b>', '']
    for emoji, emoji_id in pairs:
        lines.append(f'{html.escape(emoji)} — <code>{emoji_id}</code>')
    lines += ['', 'Пришлите эти ID Claude и напишите, на какую кнопку какой эмодзи поставить.']
    await message.answer('\n'.join(lines), parse_mode='HTML')


def register_handlers(dp: Dispatcher) -> None:
    dp.message.register(
        reply_custom_emoji_ids,
        F.chat.type == 'private',
        StateFilter(None),
        _is_admin,
        _has_custom_emoji,
    )
