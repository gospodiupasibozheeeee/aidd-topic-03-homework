from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from django.utils import timezone

from dashboard.models import Share
from investments.models import Strategy, StrategyTrade
from investments.services.portfolio import current_price

logger = logging.getLogger("investments")


class StrategyError(ValueError):
    """Raised for invalid strategy operations."""


@dataclass(frozen=True)
class StrategySummary:
    cash: Decimal
    position_quantity: Decimal
    average_price: Decimal | None
    current_price: Decimal | None
    market_value: Decimal
    equity: Decimal
    profit: Decimal
    return_percent: Decimal
    trades: int


def _decimal(value) -> Decimal:
    if value is None:
        return Decimal("0")
    return Decimal(str(value))


def evaluate_strategy(
    strategy: Strategy,
    price,
    at: datetime | None = None,
) -> StrategyTrade | None:
    """Execute a virtual buy/sell operation when the strategy conditions match.

    A buy happens only when there is no open position and the price is at or
    below ``buy_below``. A sell happens only when a position is open and the
    price is at or above ``sell_above``. This makes repeated evaluations while
    the same condition remains true idempotent.
    """

    if not strategy.is_active or price is None:
        return None

    price = _decimal(price)
    if price <= 0:
        return None
    at = at or timezone.now()

    if strategy.position_quantity == 0 and price <= strategy.buy_below:
        quantity = _decimal(strategy.quantity)
        cost = quantity * price
        if cost > strategy.cash:
            return None

        cash_after = strategy.cash - cost
        trade = StrategyTrade.objects.create(
            strategy=strategy,
            side=StrategyTrade.Side.BUY,
            price=price,
            quantity=quantity,
            executed_at=at,
            reason=f"Цена {price:.2f} ≤ порога покупки {strategy.buy_below:.2f}",
            cash_after=cash_after,
            position_after=quantity,
            pnl=Decimal("0"),
        )
        strategy.cash = cash_after
        strategy.position_quantity = quantity
        strategy.avg_price = price
        strategy.save(
            update_fields=["cash", "position_quantity", "avg_price", "updated_at"]
        )
        return trade

    if strategy.position_quantity > 0 and price >= strategy.sell_above:
        quantity = strategy.position_quantity
        average = _decimal(strategy.avg_price)
        proceeds = quantity * price
        pnl = (price - average) * quantity
        cash_after = strategy.cash + proceeds
        trade = StrategyTrade.objects.create(
            strategy=strategy,
            side=StrategyTrade.Side.SELL,
            price=price,
            quantity=quantity,
            executed_at=at,
            reason=f"Цена {price:.2f} ≥ порога продажи {strategy.sell_above:.2f}",
            cash_after=cash_after,
            position_after=Decimal("0"),
            pnl=pnl,
        )
        strategy.cash = cash_after
        strategy.position_quantity = Decimal("0")
        strategy.avg_price = None
        strategy.realized_pnl += pnl
        strategy.save(
            update_fields=[
                "cash",
                "position_quantity",
                "avg_price",
                "realized_pnl",
                "updated_at",
            ]
        )
        return trade

    return None


def evaluate_strategies(price_by_figi: dict[str, tuple[Decimal, datetime]]) -> int:
    if not price_by_figi:
        return 0

    shares = {
        share.figi: share for share in Share.objects.filter(figi__in=price_by_figi)
    }
    strategies = Strategy.objects.filter(
        is_active=True, share__in=shares.values()
    ).select_related("share")

    events = 0
    for strategy in strategies:
        data = price_by_figi.get(strategy.share.figi)
        if data is None:
            continue
        price, at = data
        try:
            if evaluate_strategy(strategy, price, at) is not None:
                events += 1
        except Exception:
            logger.exception("Strategy %s evaluation failed", strategy.pk)
    return events


def strategy_summary(strategy: Strategy) -> StrategySummary:
    price = current_price(strategy.share)
    market_value = (
        strategy.position_quantity * price if price is not None else Decimal("0")
    )
    equity = _decimal(strategy.cash) + market_value
    initial = _decimal(strategy.initial_cash)
    profit = equity - initial
    return_percent = (
        (profit / initial * Decimal("100")) if initial > 0 else Decimal("0")
    )
    return StrategySummary(
        cash=_decimal(strategy.cash),
        position_quantity=_decimal(strategy.position_quantity),
        average_price=strategy.avg_price,
        current_price=price,
        market_value=market_value,
        equity=equity,
        profit=profit,
        return_percent=return_percent,
        trades=strategy.trades.count(),
    )


def reset_strategy(strategy: Strategy) -> None:
    """Reset a simulator to its initial cash and clear its journal."""

    strategy.trades.all().delete()
    strategy.cash = strategy.initial_cash
    strategy.position_quantity = Decimal("0")
    strategy.avg_price = None
    strategy.realized_pnl = Decimal("0")
    strategy.save(
        update_fields=[
            "cash",
            "position_quantity",
            "avg_price",
            "realized_pnl",
            "updated_at",
        ]
    )
