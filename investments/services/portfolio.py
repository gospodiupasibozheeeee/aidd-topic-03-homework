from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from investments.models import Portfolio, Transaction


class PortfolioError(ValueError):
    """Raised when a transaction would make the portfolio inconsistent."""


@dataclass(frozen=True)
class Position:
    share: object
    quantity: Decimal
    average_price: Decimal
    cost_basis: Decimal
    current_price: Decimal | None
    market_value: Decimal
    unrealized_pnl: Decimal
    realized_pnl: Decimal


@dataclass(frozen=True)
class PortfolioSummary:
    total_cost: Decimal
    market_value: Decimal
    unrealized_pnl: Decimal
    realized_pnl: Decimal
    total_pnl: Decimal
    return_percent: Decimal


def _decimal(value) -> Decimal:
    if value is None:
        return Decimal("0")
    return Decimal(str(value))


def current_price(share) -> Decimal | None:
    """Return the latest known price for a share.

    ``Share.last_price`` is the primary source; if it is empty (for example
    before the first background update), the latest stored snapshot is used.
    """

    if share.last_price is not None:
        return _decimal(share.last_price)
    snapshot = share.price_snapshots.order_by("-captured_at").first()
    if snapshot is not None:
        return _decimal(snapshot.price)
    return None


def quantity_held(portfolio: Portfolio, share) -> Decimal:
    """Quantity currently held for ``share`` according to all transactions."""

    quantity = Decimal("0")
    for transaction in portfolio.transactions.filter(share=share).order_by(
        "executed_at", "id"
    ):
        if transaction.side == Transaction.Side.BUY:
            quantity += transaction.quantity
        else:
            quantity -= transaction.quantity
    return quantity


def validate_transaction(portfolio: Portfolio, share, side: str, quantity: Decimal):
    if quantity is None or quantity <= 0:
        raise PortfolioError("Количество должно быть положительным.")
    if side == Transaction.Side.SELL and quantity > quantity_held(portfolio, share):
        raise PortfolioError("Нельзя продать больше акций, чем есть в портфеле.")


def portfolio_positions(portfolio: Portfolio) -> list[Position]:
    """Calculate FIFO-independent average-cost positions."""

    states: dict[int, dict] = {}
    transactions = portfolio.transactions.select_related("share").order_by(
        "executed_at", "id"
    )

    for transaction in transactions:
        state = states.setdefault(
            transaction.share_id,
            {
                "share": transaction.share,
                "quantity": Decimal("0"),
                "cost": Decimal("0"),
                "realized": Decimal("0"),
            },
        )
        quantity = _decimal(transaction.quantity)
        price = _decimal(transaction.price)

        if transaction.side == Transaction.Side.BUY:
            state["quantity"] += quantity
            state["cost"] += quantity * price
            continue

        if quantity > state["quantity"]:
            raise PortfolioError(
                f"Продажа {quantity} {transaction.share.ticker} превышает остаток "
                f"{state['quantity']}."
            )
        average = (
            state["cost"] / state["quantity"] if state["quantity"] > 0 else Decimal("0")
        )
        state["realized"] += (price - average) * quantity
        state["quantity"] -= quantity
        state["cost"] = state["quantity"] * average

    positions: list[Position] = []
    for state in states.values():
        quantity = state["quantity"]
        average = state["cost"] / quantity if quantity > 0 else Decimal("0")
        price = current_price(state["share"])
        market_value = quantity * price if price is not None else Decimal("0")
        cost_basis = quantity * average
        positions.append(
            Position(
                share=state["share"],
                quantity=quantity,
                average_price=average,
                cost_basis=cost_basis,
                current_price=price,
                market_value=market_value,
                unrealized_pnl=market_value - cost_basis,
                realized_pnl=state["realized"],
            )
        )

    positions.sort(key=lambda position: position.share.name.lower())
    return positions


def portfolio_summary(portfolio: Portfolio) -> PortfolioSummary:
    positions = portfolio_positions(portfolio)
    total_cost = sum((position.cost_basis for position in positions), Decimal("0"))
    market_value = sum((position.market_value for position in positions), Decimal("0"))
    unrealized = market_value - total_cost
    realized = sum((position.realized_pnl for position in positions), Decimal("0"))
    total_pnl = unrealized + realized
    invested = total_cost if total_cost > 0 else Decimal("0")
    return_percent = (
        (total_pnl / invested * Decimal("100")) if invested > 0 else Decimal("0")
    )
    return PortfolioSummary(
        total_cost=total_cost,
        market_value=market_value,
        unrealized_pnl=unrealized,
        realized_pnl=realized,
        total_pnl=total_pnl,
        return_percent=return_percent,
    )
