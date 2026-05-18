"""Tests for forecast.py — weighted rolling average velocity."""

import pandas as pd
import pytest
from datetime import date, timedelta

from lib.forecast import calculate_velocity, history_metadata


def _daily_series(values, end=date(2026, 5, 18)):
    """Build a pandas Series indexed by date, ending at `end`, with the given values."""
    n = len(values)
    dates = [end - timedelta(days=n - 1 - i) for i in range(n)]
    return pd.Series(values, index=pd.to_datetime(dates), name="units")


def test_steady_velocity_returns_average():
    # 90 days of 2 units/day -> velocity ~= 2
    series = _daily_series([2] * 90)
    v = calculate_velocity(series, window_days=90, growth_factor=1.0)
    assert abs(v - 2.0) < 1e-6


def test_growth_factor_multiplies_velocity():
    series = _daily_series([2] * 90)
    v = calculate_velocity(series, window_days=90, growth_factor=1.5)
    assert abs(v - 3.0) < 1e-6


def test_growing_sales_weighted_higher_than_simple_mean():
    # Sales grow from 1 to 90 over 90 days. Weighted velocity should be > simple mean (45.5).
    series = _daily_series(list(range(1, 91)))
    v = calculate_velocity(series, window_days=90, growth_factor=1.0)
    assert v > 45.5


def test_declining_sales_weighted_lower_than_simple_mean():
    # Sales decline from 90 to 1 over 90 days. Weighted velocity should be < 45.5.
    series = _daily_series(list(range(90, 0, -1)))
    v = calculate_velocity(series, window_days=90, growth_factor=1.0)
    assert v < 45.5


def test_no_sales_returns_zero():
    series = _daily_series([0] * 90)
    v = calculate_velocity(series, window_days=90, growth_factor=1.0)
    assert v == 0.0


def test_empty_series_returns_zero():
    series = pd.Series([], dtype=float, index=pd.to_datetime([]))
    v = calculate_velocity(series, window_days=90, growth_factor=1.0)
    assert v == 0.0


def test_history_metadata_for_new_sku():
    # SKU with first sale 5 days ago
    series = _daily_series([0] * 85 + [1, 0, 0, 0, 1])
    meta = history_metadata(series, today=date(2026, 5, 18))
    assert meta["days_since_first_sale"] == 4   # last 5 days, first sale was 4 days before today
    assert meta["days_since_last_sale"] == 0


def test_history_metadata_for_dead_sku():
    # SKU sold once 70 days ago, nothing since
    series = _daily_series([0] * 20 + [1] + [0] * 69)
    meta = history_metadata(series, today=date(2026, 5, 18))
    assert meta["days_since_last_sale"] == 69
