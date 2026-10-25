"""Админ присылает боту анимированные эмодзи — бот отвечает их ID (для иконок кнопок)."""

from __future__ import annotations

from unittest.mock import AsyncMock

from aiogram.types import Chat, Message, MessageEntity, User

from app.handlers.admin import emoji_ids


def _message(text: str, entities: list[MessageEntity]) -> Message:
    return Message(
        message_id=1,
        date=0,
        chat=Chat(id=1, type='private'),
        from_user=User(id=1, is_bot=False, first_name='A'),
        text=text,
        entities=entities,
    )


def test_extracts_custom_emoji_ids_in_order_without_duplicates() -> None:
    text = '🔥 и 💎 и 🔥'
    entities = [
        MessageEntity(type='custom_emoji', offset=0, length=2, custom_emoji_id='111'),
        MessageEntity(type='custom_emoji', offset=5, length=2, custom_emoji_id='222'),
        MessageEntity(type='custom_emoji', offset=10, length=2, custom_emoji_id='111'),
    ]
    assert [eid for _, eid in emoji_ids.custom_emoji_ids(_message(text, entities))] == ['111', '222']


def test_plain_emoji_are_ignored() -> None:
    msg = _message('🔥 просто текст', [MessageEntity(type='bold', offset=0, length=2)])
    assert emoji_ids.custom_emoji_ids(msg) == []
    assert emoji_ids._has_custom_emoji(msg) is False


async def test_reply_lists_ids(monkeypatch) -> None:
    msg = _message('🔥', [MessageEntity(type='custom_emoji', offset=0, length=2, custom_emoji_id='111')])
    answer = AsyncMock()
    monkeypatch.setattr(Message, 'answer', answer)
    await emoji_ids.reply_custom_emoji_ids(msg)
    sent = answer.await_args.args[0]
    assert '<code>111</code>' in sent
