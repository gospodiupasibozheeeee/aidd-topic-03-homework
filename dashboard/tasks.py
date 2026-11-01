import logging
from itertools import islice

from celery import shared_task
from django.conf import settings
from django.db.models import BooleanField, Case, Q, Value, When

from dashboard.models import Share
from dashboard.services.client import (
    MarketDataClient,
    MarketDataError,
    quotation_time,
    quotation_to_decimal,
)

logger = logging.getLogger("main")


@shared_task
def update_last_price():
    if not settings.TINKOFF_TOKEN:
        logger.warning("Price refresh skipped: TINKOFF_TOKEN is not configured")
        return 0
    updated = 0
    shares = iter(
        Share.objects.order_by("pk").only("pk", "figi").iterator(chunk_size=100)
    )
    with MarketDataClient() as client:
        while batch := list(islice(shares, 100)):
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
                    # Older quotes cannot overwrite a newer stored observation.
                    count = (
                        Share.objects.filter(pk=share.pk)
                        .filter(
                            Q(last_price__isnull=True)
                            | Q(updated_at__isnull=True)
                            | Q(updated_at__lte=timestamp)
                        )
                        .update(
                            last_price=price,
                            # Compare against the value stored at UPDATE time,
                            # including changes made by another worker.
                            is_trend_high=Case(
                                When(last_price__lt=price, then=Value(True)),
                                When(last_price__gt=price, then=Value(False)),
                                default=Value(None),
                                output_field=BooleanField(),
                            ),
                            updated_at=timestamp,
                        )
                    )
                    updated += count
                except (KeyError, TypeError, MarketDataError) as exc:
                    logger.warning("Price unavailable for share %s: %s", share.pk, exc)
    return updated
