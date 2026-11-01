from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from investing.models import Notification, WatchItem


@transaction.atomic
def save_watch_item(
    owner,
    *,
    watchlist,
    share,
    target=None,
    direction=WatchItem.Direction.ABOVE,
    item_id=None,
):
    if watchlist.owner_id != owner.pk:
        raise PermissionDenied
    if item_id is None:
        item = WatchItem(watchlist=watchlist)
    else:
        item = WatchItem.objects.select_for_update(of=("self",)).get(
            pk=item_id, watchlist__owner=owner
        )
        if item.watchlist_id != watchlist.pk:
            raise ValidationError("Нельзя переместить запись в другой список.")
        if (item.share_id, item.target, item.direction) != (
            share.pk,
            target,
            direction,
        ):
            item.revision += 1
            item.triggered_at = None
    item.share, item.target, item.direction = share, target, direction
    item.full_clean()
    item.save()
    return item


def evaluate_alerts(point):
    items = (
        WatchItem.objects.select_for_update(of=("self",))
        .filter(
            share_id=point.share_id,
            target__isnull=False,
            triggered_at__isnull=True,
        )
        .select_related("watchlist", "share")
        .order_by("pk")
    )
    for item in items:
        reached = (
            point.price >= item.target
            if item.direction == WatchItem.Direction.ABOVE
            else point.price <= item.target
        )
        if not reached:
            continue
        symbol = "≥" if item.direction == WatchItem.Direction.ABOVE else "≤"
        Notification.objects.get_or_create(
            event_key=f"watch:{item.pk}:{item.revision}",
            defaults={
                "owner_id": item.watchlist.owner_id,
                "item": item,
                "price": point.price,
                "observed_at": point.observed_at,
                "message": f"{item.share.ticker}: {point.price} {item.share.currency} {symbol} {item.target}",
            },
        )
        item.triggered_at = point.observed_at
        item.save(update_fields=["triggered_at"])
