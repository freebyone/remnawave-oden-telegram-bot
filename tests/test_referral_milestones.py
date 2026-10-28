"""Разовые бонусы за оплативших друзей и полоса прогресса экрана рефералки."""

from app.config import settings
from app.services.referral_reward_service import render_progress_bar


def test_milestones_parsed_sorted_and_bad_pairs_skipped(monkeypatch):
    monkeypatch.setattr(settings, 'REFERRAL_MILESTONES', '10:180, 3:30,oops,20:365,5:0,:7')
    assert settings.get_referral_milestones() == [(3, 30), (10, 180), (20, 365)]


def test_milestones_empty_means_disabled(monkeypatch):
    monkeypatch.setattr(settings, 'REFERRAL_MILESTONES', '')
    assert settings.get_referral_milestones() == []


def test_progress_bar_fills_proportionally():
    assert render_progress_bar(0, 3) == '▱' * 10
    assert render_progress_bar(1, 3) == '▰' * 3 + '▱' * 7
    assert render_progress_bar(3, 3) == '▰' * 10
    assert render_progress_bar(5, 3) == '▰' * 10
    assert render_progress_bar(2, 0) == '▰' * 10
