from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from dashboard.models import Share
from investments.services.history import record_snapshot
from investments.services.strategy import evaluate_strategies
from investments.services.watchlist import evaluate_watchlist

logger = logging.getLogger("investments")


@dataclass(frozen=True)
class MarketUpdateResult:
    snapshots: int
    watchlist_events: int
    strategy_events: int


def process_market_updates(
    prices: dict[str, tuple[Decimal, datetime]],
) -> MarketUpdateResult:
    """Persist prices and run personal rules after a market update.

    Called by the Celery price task after ``Share.last_price`` is refreshed.
    The function is intentionally independent from the task so it can be tested
    and reused by a management command.
    """

    if not prices:
        return MarketUpdateResult(0, 0, 0)

    shares = Share.objects.in_bulk(field_name="figi")
    snapshots = 0

    for figi, data in prices.items():
        share = shares.get(figi)
        if share is None:
            continue
        price, captured_at = data
        try:
            if record_snapshot(share, price, captured_at=captured_at) is not None:
                snapshots += 1
        except Exception:
            logger.exception("Could not save price snapshot for %s", figi)

    watchlist_events = evaluate_watchlist(prices)
    strategy_events = evaluate_strategies(prices)

    return MarketUpdateResult(
        snapshots=snapshots,
        watchlist_events=watchlist_events,
        strategy_events=strategy_events,
    )
