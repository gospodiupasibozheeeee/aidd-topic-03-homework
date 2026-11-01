from __future__ import annotations

import logging
from datetime import datetime

from django.utils import timezone

from config.celery import app

from .models import Share
from .services.market_data import get_last_prices

logger = logging.getLogger("dashboard")


@app.task
def update_last_price() -> int:
    """Refresh prices for every share in one batch request.

    The previous implementation created a new gRPC client and a separate
    request for every share. A single ``get_last_prices`` call is used here;
    failures are logged without interrupting the remaining rows.
    """

    shares = list(Share.objects.all())
    if not shares:
        return 0

    try:
        prices = get_last_prices(shares)
    except Exception as exc:
        logger.exception("Could not load market prices: %s", exc)
        return 0

    updated = 0
    for share in shares:
        data = prices.get(share.figi)
        if data is None:
            continue

        new_price, price_time = data
        old_price = share.last_price
        is_trend_high = True if old_price is None else new_price >= old_price

        if isinstance(price_time, datetime):
            if timezone.is_naive(price_time):
                price_time = timezone.make_aware(price_time, timezone.utc)
        else:
            price_time = timezone.now()

        Share.objects.filter(pk=share.pk).update(
            last_price=new_price,
            is_trend_high=is_trend_high,
            updated_at=price_time,
        )
        updated += 1

    try:
        from investments.services.market_events import process_market_updates

        event_result = process_market_updates(prices)
        logger.info(
            "Market events: snapshots=%s watchlist=%s strategies=%s",
            event_result.snapshots,
            event_result.watchlist_events,
            event_result.strategy_events,
        )
    except Exception:
        logger.exception("Could not process post-price market events")

    logger.info("Updated prices for %s of %s shares", updated, len(shares))
    return updated
