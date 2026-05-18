"""Tests for reorder.py — status logic and recommended quantity."""

import math
import pytest

from lib.reorder import (
    ReorderRecommendation,
    Settings,
    compute_recommendation,
)


# Default settings matching schema.sql defaults
DEFAULTS = Settings(
    reorder_now_days=30,
    reorder_soon_days=45,
    slow_mover_threshold=0.10,
    dead_mover_days=60,
    insufficient_history_days=14,
)


def _rec(on_hand, velocity, days_first=None, days_last=None, moq=1, target_cover=60, manual=False, settings=DEFAULTS):
    return compute_recommendation(
        sku="LUM-TEST-001",
        on_hand=on_hand,
        daily_velocity=velocity,
        days_since_first_sale=days_first if days_first is not None else 365,
        days_since_last_sale=days_last if days_last is not None else 1,
        moq=moq,
        target_cover_days=target_cover,
        manual_override=manual,
        settings=settings,
    )


def test_healthy_above_soon_threshold():
    # 60 days of supply -> healthy (above 45)
    r = _rec(on_hand=60, velocity=1.0)
    assert r.status == "healthy"


def test_reorder_soon_at_45_days():
    # exactly 45 days of supply -> reorder_soon (boundary inclusive)
    r = _rec(on_hand=45, velocity=1.0)
    assert r.status == "reorder_soon"


def test_reorder_soon_at_31_days():
    # 31 days of supply -> reorder_soon (above 30 but at/below 45)
    r = _rec(on_hand=31, velocity=1.0)
    assert r.status == "reorder_soon"


def test_reorder_now_at_30_days():
    # exactly 30 days of supply -> reorder_now (boundary inclusive)
    r = _rec(on_hand=30, velocity=1.0)
    assert r.status == "reorder_now"


def test_reorder_now_when_out_of_stock():
    r = _rec(on_hand=0, velocity=1.0)
    assert r.status == "reorder_now"
    assert r.days_of_supply == 0.0


def test_negative_on_hand_treated_as_zero():
    r = _rec(on_hand=-3, velocity=1.0)
    assert r.status == "reorder_now"
    assert r.days_of_supply == 0.0


def test_slow_mover_excluded_from_reorder_alerts():
    # velocity below threshold -> slow, even if on_hand is low in absolute terms
    r = _rec(on_hand=5, velocity=0.05)
    assert r.status == "slow"


def test_dead_mover_after_long_zero_sales():
    # velocity zero and last sale was 70 days ago -> dead
    r = _rec(on_hand=10, velocity=0.0, days_last=70)
    assert r.status == "dead"


def test_zero_velocity_with_recent_sale_is_slow_not_dead():
    r = _rec(on_hand=10, velocity=0.0, days_last=10)
    assert r.status == "slow"


def test_insufficient_history_when_sku_too_new():
    # First sale 5 days ago -> insufficient history
    r = _rec(on_hand=10, velocity=1.0, days_first=5)
    assert r.status == "insufficient_history"


def test_manual_override_skips_status_logic():
    r = _rec(on_hand=0, velocity=1.0, manual=True)
    assert r.status == "manual_override"


def test_recommended_qty_uses_target_cover_when_high_velocity():
    # velocity 2/day * 60-day cover = 120 units, well above MOQ=10
    r = _rec(on_hand=10, velocity=2.0, moq=10, target_cover=60)
    assert r.recommended_qty == 120


def test_recommended_qty_floored_at_moq():
    # velocity 0.1/day * 60-day cover = 6 units, MOQ=12 -> use MOQ
    r = _rec(on_hand=2, velocity=0.1, moq=12, target_cover=60)
    assert r.recommended_qty == 12


def test_days_of_supply_infinity_when_velocity_zero_and_stock_present():
    r = _rec(on_hand=100, velocity=0.0, days_last=5)
    assert r.days_of_supply is None  # represents infinity


def test_velocity_rounded_in_recommended_qty():
    # velocity 1.7 * 60 = 102 -> recommended_qty 102
    r = _rec(on_hand=20, velocity=1.7, moq=1, target_cover=60)
    assert r.recommended_qty == 102
