from __future__ import annotations

import logging

from .tinkoff import MarketDataError, get_last_prices, quotation_to_decimal

logger = logging.getLogger("dashboard")


def get_last_data(share):
    """Return ``(price, time)`` for a single share.

    Kept as a backwards-compatible wrapper used by older callers/tests; the
    background task uses :func:`get_last_prices` to batch requests.
    """

    prices = get_last_prices([share])
    if share.figi not in prices:
        raise MarketDataError(f"Нет цены для {share.ticker} ({share.figi})")
    logger.info("Get last data for share with id %s", share.id)
    return prices[share.figi]


__all__ = [
    "MarketDataError",
    "get_last_data",
    "get_last_prices",
    "quotation_to_decimal",
]
