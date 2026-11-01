from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from dashboard.models import Share
from investing.models import PricePoint

from .monitoring import evaluate_alerts
from .strategies import evaluate_strategies
from .trading import money_value


@transaction.atomic
def record_quote(share_id, price, observed_at):
    price = money_value(price)
    if timezone.is_naive(observed_at):
        raise ValidationError("Время котировки должно включать часовой пояс.")
    share = Share.objects.select_for_update().get(pk=share_id)
    point, _ = PricePoint.objects.get_or_create(
        share=share,
        observed_at=observed_at,
        defaults={"price": price, "currency": share.currency.lower()},
    )
    # The first stored payload is canonical for a source timestamp.
    price = point.price
    if point.currency != share.currency.lower():
        return False
    previous_time = share.market_updated_at or (
        share.updated_at if share.last_price is not None else None
    )
    if previous_time is not None and observed_at < previous_time:
        return False
    changed = share.market_updated_at is None or observed_at > share.market_updated_at
    if changed:
        direction = (
            None
            if share.last_price is None or share.last_price == price
            else price > share.last_price
        )
        Share.objects.filter(pk=share.pk).update(
            last_price=price,
            is_trend_high=direction,
            updated_at=observed_at,
            market_updated_at=observed_at,
        )
    # Re-evaluate newly configured rules on repeated current quotes. Event keys
    # and rule state make existing alerts and executions idempotent.
    evaluate_alerts(point)
    evaluate_strategies(point)
    return changed
