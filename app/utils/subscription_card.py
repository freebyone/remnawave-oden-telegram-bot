"""Card text and management buttons for a single subscription.

Shared by the standalone management screen (sm:{id}) in
app/handlers/subscription/my_subscriptions.py and «Мой профиль» in
app/handlers/menu.py. Kept outside app/handlers so that the profile can use it
without importing the subscription handlers, which pull in the payment
modules and close an import cycle (see tests/services/test_cashera_import_cycle.py).
"""

from __future__ import annotations

from aiogram import types

from app.config import settings
from app.localization.texts import Texts
from app.utils.timezone import format_local_datetime


def build_subscription_action_rows(sub_id: int, sub=None) -> list[list[types.InlineKeyboardButton]]:
    """Management buttons for one subscription, without a back button.

    For expired/disabled subscriptions, only 'Renew' and 'Delete' are shown —
    connection link and traffic/device management are irrelevant.
    """
    is_inactive = sub is not None and sub.actual_status in ('expired', 'disabled')

    buttons = []

    if not is_inactive:
        buttons.append([types.InlineKeyboardButton(text='🔗 Ссылка подключения', callback_data=f'sl:{sub_id}')])

    buttons.append([types.InlineKeyboardButton(text='🔄 Продлить', callback_data=f'se:{sub_id}')])

    if not is_inactive:
        buttons.append([types.InlineKeyboardButton(text='💳 Автоплатеж', callback_data='subscription_autopay')])
        buttons.append([types.InlineKeyboardButton(text='📊 Трафик', callback_data=f'st:{sub_id}')])
        buttons.append([types.InlineKeyboardButton(text='📱 Устройства', callback_data=f'sd:{sub_id}')])

    if is_inactive:
        buttons.append([types.InlineKeyboardButton(text='🗑 Удалить подписку', callback_data=f'sub_del:{sub_id}')])

    if not is_inactive and settings.is_subscription_revoke_enabled():
        buttons.append(
            [
                types.InlineKeyboardButton(
                    text='🔄 Перевыпустить',
                    callback_data=f'sr:{sub_id}',
                )
            ]
        )

    return buttons


def format_subscription_detail_text(subscription) -> str:
    """Subscription card: tariff, status, traffic, devices, end date and link."""
    tariff_name = subscription.tariff.name if subscription.tariff else 'Подписка'

    if subscription.traffic_limit_gb == 0:
        traffic = '∞ ГБ'
    else:
        used = f'{subscription.traffic_used_gb:.1f}' if subscription.traffic_used_gb else '0'
        traffic = f'{used} / {subscription.traffic_limit_gb} ГБ'

    end_date = format_local_datetime(subscription.end_date, '%d.%m.%Y %H:%M') if subscription.end_date else '—'
    status = subscription.status_display

    text = (
        f'📋 <b>{tariff_name}</b>\n\n'
        f'Статус: {status}\n'
        f'📊 Трафик: {traffic}\n'
        f'📱 Устройства: {Texts.format_device_limit(subscription.device_limit)}\n'
        f'📅 До: {end_date}\n'
    )

    if subscription.subscription_url and not settings.should_hide_subscription_link():
        text += f'\n🔗 <code>{subscription.subscription_url}</code>'

    return text
