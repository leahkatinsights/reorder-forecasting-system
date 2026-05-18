"""Forecasting: weighted rolling average daily velocity per SKU."""

from datetime import date
from typing import TypedDict

import numpy as np
import pandas as pd


class HistoryMeta(TypedDict):
    days_since_first_sale: int | None
    days_since_last_sale: int | None


def calculate_velocity(
    daily_sales: pd.Series,
    window_days: int = 90,
    growth_factor: float = 1.0,
) -> float:
    """Return weighted-average daily velocity (units/day) for a SKU.

    Weights ramp linearly from 0.5 (oldest day in window) to 1.5 (most recent day),
    so the average weight is 1.0 and recent days count for more.

    Args:
        daily_sales: pandas Series indexed by date, values = units sold per day.
                     Should cover at least `window_days` consecutive days.
        window_days: how many recent days to include.
        growth_factor: multiplier applied to the final velocity.

    Returns:
        Velocity in units/day. Zero if series is empty or fully zero.
    """
    if daily_sales.empty:
        return 0.0

    recent = daily_sales.tail(window_days)
    n = len(recent)
    if n == 0:
        return 0.0

    weights = np.linspace(0.5, 1.5, n)
    weighted_avg = float(np.average(recent.values, weights=weights))
    return weighted_avg * growth_factor


def history_metadata(daily_sales: pd.Series, today: date) -> HistoryMeta:
    """Return how many days since the SKU first sold and last sold.

    Args:
        daily_sales: pandas Series indexed by date, values = units sold per day.
        today: reference date for the diff.

    Returns:
        days_since_first_sale: int or None if SKU has never sold.
        days_since_last_sale: int or None if SKU has never sold.
    """
    nonzero = daily_sales[daily_sales > 0]
    if nonzero.empty:
        return HistoryMeta(days_since_first_sale=None, days_since_last_sale=None)

    first = nonzero.index.min().date()
    last = nonzero.index.max().date()
    return HistoryMeta(
        days_since_first_sale=(today - first).days,
        days_since_last_sale=(today - last).days,
    )
