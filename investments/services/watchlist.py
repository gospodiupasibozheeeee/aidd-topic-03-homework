from __future__ import annotations

import logging
from datetime import datetime
from decimal import Decimal

from django.utils import timezone

from dashboard.models import Share
from investments.models import Notification, WatchlistItem

logger = logging.getLogger("investments")


def _decimal(value) -> Decimal:
    return Decimal(str(value))


def evaluate_item(
    item: WatchlistItem,
    price,
    at: datetime | None = None,
) -> bool:
    """Evaluate one watchlist item and create at most one notification per event.

    ``alert_active`` prevents repeated notifications while the condition stays
    true. ``alert_epoch`` is incremented on every false->true transition so a
    later re-crossing creates a genuinely new event, while ``dedupe_key`` keeps
    the notification creation idempotent.
    """

    if not item.is_active or item.target_price is None or price is None:
        return False

    price = _decimal(price)
    target = _decimal(item.target_price)
    triggered = (
        price >= target
        if item.direction == WatchlistItem.Direction.ABOVE
        else price <= target
    )

    if triggered and not item.alert_active:
        item.alert_active = True
        item.alert_epoch += 1
        item.last_notified_at = at or timezone.now()
        item.save(update_fields=["alert_active", "alert_epoch", "last_notified_at"])

        direction = (
            "выше" if item.direction == WatchlistItem.Direction.ABOVE else "ниже"
        )
        Notification.objects.get_or_create(
            dedupe_key=(
                f"watchlist:{item.pk}:{item.target_price}:"
                f"{item.direction}:{item.alert_epoch}"
            ),
            defaults={
                "user": item.watchlist.user,
                "kind": Notification.Kind.WATCHLIST,
                "title": f"{item.share.ticker}: целевая цена достигнута",
                "message": (
                    f"Цена {item.share.ticker} равна {price:.2f} и {direction} "
                    f"целевого уровня {target:.2f}."
                ),
                "share": item.share,
            },
        )
        return True

    if not triggered and item.alert_active:
        item.alert_active = False
        item.save(update_fields=["alert_active"])

    return False


def evaluate_watchlist(price_by_figi: dict[str, tuple[Decimal, datetime]]) -> int:
    """Evaluate all active watchlist items for the supplied prices."""

    if not price_by_figi:
        return 0

    shares = {
        share.figi: share for share in Share.objects.filter(figi__in=price_by_figi)
    }
    items = WatchlistItem.objects.filter(
        is_active=True,
        target_price__isnull=False,
        share__in=shares.values(),
    ).select_related("watchlist__user", "share")

    events = 0
    for item in items:
        data = price_by_figi.get(item.share.figi)
        if data is None:
            continue
        price, at = data
        try:
            if evaluate_item(item, price, at):
                events += 1
        except Exception:
            # One malformed item must not block other notifications.
            logger.exception("Watchlist item %s evaluation failed", item.pk)
    return events


def unread_count(user) -> int:
    return Notification.objects.filter(user=user, is_read=False).count()
