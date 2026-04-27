"""
Shelf Life calculation utility.

Formula (derived from Shelf_Life.xlsx):
  Total Days   = Expiry Date - Manufacturing Date
  Remaining    = Expiry Date - Inward Date
  Shelf Life % = (Remaining / Total Days) × 100

If Total Days <= 0, returns 0.0 to avoid division by zero.
"""

from datetime import date


def calculate_shelf_life(
    mfg_date: date,
    expiry_date: date,
    inward_date: date,
) -> float:
    """
    Calculate shelf life percentage remaining at inward date.

    Args:
        mfg_date:     Manufacturing / Production date
        expiry_date:  Expiry / Best Before date
        inward_date:  Date of inward at warehouse (or port)

    Returns:
        Shelf life percentage (float, 0–100+).
        Negative values indicate product has already expired at inward.
    """
    total_days = (expiry_date - mfg_date).days
    if total_days <= 0:
        return 0.0

    remaining = (expiry_date - inward_date).days
    shelf_pct = round((remaining / total_days) * 100, 2)
    return shelf_pct


def shelf_life_status(shelf_pct: float, threshold: float) -> str:
    """
    Return a status string based on shelf life % vs threshold.

    Args:
        shelf_pct:  Calculated shelf life percentage
        threshold:  Configured threshold percentage

    Returns:
        'OK', 'BELOW THRESHOLD', or 'EXPIRED'
    """
    if shelf_pct <= 0:
        return "EXPIRED"
    if shelf_pct < threshold:
        return "BELOW THRESHOLD"
    return "OK"
