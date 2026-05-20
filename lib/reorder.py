"""Reorder status logic and recommended quantity calculation."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    reorder_now_days: int = 30
    reorder_soon_days: int = 45
    slow_mover_threshold: float = 0.10
    dead_mover_days: int = 60
    insufficient_history_days: int = 14


@dataclass(frozen=True)
class ReorderRecommendation:
    sku: str
    on_hand: int
    daily_velocity: float
    days_of_supply: float | None   # None represents infinity (zero velocity with stock)
    status: str                    # see STATUS_VALUES
    recommended_qty: int


STATUS_VALUES = {
    "reorder_now",
    "reorder_soon",
    "healthy",
    "slow",
    "dead",
    "insufficient_history",
    "manual_override",
    "on_order",
}


def compute_recommendation(
    sku: str,
    on_hand: int,
    daily_velocity: float,
    days_since_first_sale: int | None,
    days_since_last_sale: int | None,
    moq: int,
    target_cover_days: int,
    manual_override: bool,
    settings: Settings,
) -> ReorderRecommendation:
    """Compute the reorder recommendation for a single SKU.

    Args:
        sku: Product SKU.
        on_hand: Current inventory; negatives are clamped to 0 for the calculation.
        daily_velocity: Weighted-average daily velocity (units/day), already growth-adjusted.
        days_since_first_sale: Days since the SKU first sold. None if never sold.
        days_since_last_sale: Days since the SKU's most recent sale. None if never sold.
        moq: Vendor minimum order quantity (>=1).
        target_cover_days: How many days of stock the recommended order should cover.
        manual_override: If True, status is forced to 'manual_override'.
        settings: Global thresholds.

    Returns:
        ReorderRecommendation with computed status, days_of_supply, and recommended_qty.
    """
    on_hand_clamped = max(on_hand, 0)

    # days_of_supply: None means infinite (zero velocity, stock on hand).
    if daily_velocity > 0:
        days_of_supply = on_hand_clamped / daily_velocity
    else:
        days_of_supply = None

    status = _compute_status(
        on_hand_clamped=on_hand_clamped,
        daily_velocity=daily_velocity,
        days_of_supply=days_of_supply,
        days_since_first_sale=days_since_first_sale,
        days_since_last_sale=days_since_last_sale,
        manual_override=manual_override,
        settings=settings,
    )

    recommended_qty = max(moq, round(target_cover_days * daily_velocity))

    return ReorderRecommendation(
        sku=sku,
        on_hand=on_hand,
        daily_velocity=daily_velocity,
        days_of_supply=days_of_supply,
        status=status,
        recommended_qty=recommended_qty,
    )


def _compute_status(
    on_hand_clamped: int,
    daily_velocity: float,
    days_of_supply: float | None,
    days_since_first_sale: int | None,
    days_since_last_sale: int | None,
    manual_override: bool,
    settings: Settings,
) -> str:
    if manual_override:
        return "manual_override"

    # Dead: no sales for > dead_mover_days
    if days_since_last_sale is not None and days_since_last_sale > settings.dead_mover_days:
        return "dead"
    if days_since_last_sale is None:
        # never sold = also dead
        return "dead"

    # Insufficient history: SKU is too new to forecast reliably
    if days_since_first_sale is not None and days_since_first_sale < settings.insufficient_history_days:
        return "insufficient_history"

    # Slow mover: velocity below threshold (excludes from auto alerts).
    # Comes before reorder_now because slow movers shouldn't appear as alerts
    # even when on_hand is technically low.
    if daily_velocity < settings.slow_mover_threshold:
        return "slow"

    # Out of stock with active velocity -> reorder now
    if on_hand_clamped == 0:
        return "reorder_now"

    assert days_of_supply is not None  # velocity > slow_mover_threshold > 0
    if days_of_supply <= settings.reorder_now_days:
        return "reorder_now"
    if days_of_supply <= settings.reorder_soon_days:
        return "reorder_soon"
    return "healthy"
