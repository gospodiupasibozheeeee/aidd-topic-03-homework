import uuid
from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Sum

from investing.models import Strategy, StrategyRun

from .trading import execute_trade, rounded


@transaction.atomic
def save_strategy(
    owner,
    *,
    portfolio,
    share,
    name,
    quantity,
    buy_below,
    sell_above,
    active=True,
    strategy_id=None,
):
    if portfolio.owner_id != owner.pk:
        raise PermissionDenied
    if strategy_id is None:
        strategy = Strategy(portfolio=portfolio, share=share)
    else:
        strategy = Strategy.objects.select_for_update(of=("self",)).get(
            pk=strategy_id, portfolio__owner=owner
        )
        if strategy.portfolio_id != portfolio.pk or strategy.share_id != share.pk:
            raise ValidationError("Портфель и акция существующей стратегии неизменны.")
    for field, value in dict(
        name=name,
        quantity=quantity,
        buy_below=buy_below,
        sell_above=sell_above,
        active=active,
    ).items():
        setattr(strategy, field, value)
    strategy.full_clean()
    strategy.save()
    return strategy


def evaluate_strategies(point):
    # Consistent portfolio order prevents crossed locks between different quotes.
    ids = list(
        Strategy.objects.filter(share_id=point.share_id, active=True)
        .order_by("portfolio_id", "pk")
        .values_list("pk", flat=True)
    )
    for identifier in ids:
        strategy = (
            Strategy.objects.select_for_update(of=("self",))
            .filter(pk=identifier, active=True)
            .select_related("portfolio")
            .first()
        )
        if strategy is None:
            continue
        action = strategy.next_action
        matches = (
            point.price <= strategy.buy_below
            if action == Strategy.Action.BUY
            else point.price >= strategy.sell_above
        )
        if not matches:
            continue
        key = f"strategy:{strategy.pk}:quote:{point.pk}"
        if StrategyRun.objects.filter(event_key=key).exists():
            continue
        run = StrategyRun(
            strategy=strategy,
            strategy_name=strategy.name,
            portfolio=strategy.portfolio,
            quote=point,
            event_key=key,
            action=action,
        )
        try:
            with transaction.atomic():
                quantity = (
                    strategy.quantity
                    if action == Strategy.Action.BUY
                    else strategy.cycle_quantity
                )
                trade, _ = execute_trade(
                    strategy.portfolio.owner,
                    strategy.portfolio_id,
                    strategy.share_id,
                    action,
                    quantity,
                    uuid.uuid5(uuid.NAMESPACE_URL, key),
                    price=point.price,
                    strategy=strategy,
                )
                run.status, run.trade = "executed", trade
                if action == Strategy.Action.BUY:
                    strategy.next_action = Strategy.Action.SELL
                    strategy.cycle_quantity, strategy.cycle_cost = (
                        trade.quantity,
                        trade.amount,
                    )
                else:
                    run.profit = trade.amount - strategy.cycle_cost
                    strategy.next_action = Strategy.Action.BUY
                    strategy.cycle_quantity, strategy.cycle_cost = 0, Decimal(0)
                strategy.save(
                    update_fields=["next_action", "cycle_quantity", "cycle_cost"]
                )
        except ValidationError as exc:
            run.status = "rejected"
            run.reason = "; ".join(exc.messages)[:300]
        run.save()


def strategy_summary(strategy):
    runs = strategy.runs.all()
    return {
        "executed": runs.filter(status="executed").count(),
        "rejected": runs.filter(status="rejected").count(),
        "profit": rounded(
            runs.aggregate(total=Sum("profit", default=Decimal(0)))["total"]
        ),
    }
