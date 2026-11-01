import logging

from celery import shared_task
from django.conf import settings
from django.core.exceptions import ValidationError

from dashboard.models import Share
from dashboard.services.client import (
    MarketDataClient,
    MarketDataError,
    quotation_time,
    quotation_to_decimal,
)
from investing.services.prices import record_quote

logger = logging.getLogger("main")


@shared_task
def update_last_price():
    if not settings.TINKOFF_TOKEN:
        logger.warning("Price refresh skipped: TINKOFF_TOKEN is not configured")
        return 0
    updated = 0
    last_pk = 0
    with MarketDataClient() as client:
        while True:
            # Materialize and close the read cursor before network calls and
            # writes; an open SQLite iterator can block another writer's commit.
            batch = list(
                Share.objects.filter(pk__gt=last_pk)
                .order_by("pk")
                .only("pk", "figi")[:100]
            )
            if not batch:
                break
            last_pk = batch[-1].pk
            try:
                response = client.last_prices([share.figi for share in batch])
                prices = {
                    quote["figi"]: quote
                    for quote in response
                    if isinstance(quote, dict) and "figi" in quote
                }
            except MarketDataError as exc:
                logger.warning("Price batch failed: %s", exc)
                continue
            for share in batch:
                try:
                    quote = prices[share.figi]
                    price = quotation_to_decimal(quote["price"])
                    timestamp = quotation_time(quote["time"])
                    updated += record_quote(share.pk, price, timestamp)
                except (
                    KeyError,
                    TypeError,
                    MarketDataError,
                    ValidationError,
                    Share.DoesNotExist,
                ) as exc:
                    logger.warning("Price unavailable for share %s: %s", share.pk, exc)
    return updated
