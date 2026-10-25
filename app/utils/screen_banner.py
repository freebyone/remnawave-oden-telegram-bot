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
