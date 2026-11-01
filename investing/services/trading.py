import uuid
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation, localcontext

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Sum

from dashboard.models import Share
from investing.models import QUANTUM, Portfolio, Position, Strategy, Trade

MAX_MONEY = Decimal("999999999999999.999999999")


class TradeConflict(ValidationError):
    pass


def rounded(value):
    with localcontext() as context:
        context.prec = 50
        return value.quantize(QUANTUM, rounding=ROUND_HALF_UP)


def money_value(value, *, positive=False, signed=False):
    try:
        number = Decimal(str(value))
        if not number.is_finite() or abs(number) > MAX_MONEY:
            raise ValueError
        number = rounded(number)
        if (positive and number <= 0) or (not signed and number < 0):
            raise ValueError
        return number
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValidationError("Некорректная сумма или цена.") from exc


def percent(change, base):
    if not base:
        return None
    with localcontext() as context:
        context.prec = 50
        return rounded(change * 100 / base)


@transaction.atomic
def create_portfolio(owner, *, name, currency, initial_cash):
    amount = money_value(initial_cash)
    portfolio = Portfolio(
        owner=owner,
        name=name.strip(),
        currency=currency.strip().lower(),
        initial_cash=amount,
        cash=amount,
    )
    portfolio.full_clean()
    portfolio.save()
    return portfolio


@transaction.atomic
def execute_trade(
    owner,
    portfolio_id,
    share_id,
    side,
    quantity,
    request_id,
    *,
    price=None,
    strategy=None,
):
    if type(quantity) is not int or not 1 <= quantity <= 2147483647:
        raise ValidationError("Количество должно быть положительным целым числом.")
    if side not in Strategy.Action.values:
        raise ValidationError("Неизвестная операция.")
    try:
        request_id = uuid.UUID(str(request_id))
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValidationError("Для сделки необходим корректный UUID запроса.") from exc
    # All writers take the share lock before the portfolio lock.
    try:
        share = Share.objects.select_for_update().get(pk=share_id)
    except Share.DoesNotExist as exc:
        raise ValidationError("Акция больше не доступна.") from exc
    try:
        portfolio = Portfolio.objects.select_for_update().get(
            pk=portfolio_id, owner=owner
        )
    except Portfolio.DoesNotExist as exc:
        raise PermissionDenied from exc
    existing = Trade.objects.filter(portfolio=portfolio, request_id=request_id).first()
    if existing:
        if (
            existing.share_id != share_id
            or existing.side != side
            or existing.quantity != quantity
            or (
                price is not None
                and existing.price != money_value(price, positive=True)
            )
        ):
            raise TradeConflict(
                "Эта форма уже отправлена с другими параметрами. Откройте новую форму сделки."
            )
        return existing, False
    if share.currency.lower() != portfolio.currency.lower():
        raise ValidationError("Валюты акции и портфеля должны совпадать.")
    price = money_value(share.last_price if price is None else price, positive=True)
    amount = money_value(price * quantity, positive=True)
    position, _ = Position.objects.get_or_create(portfolio=portfolio, share=share)
    realized = Decimal(0)
    if side == Strategy.Action.BUY:
        if amount > portfolio.cash:
            raise ValidationError("Недостаточно виртуальных денег.")
        if position.quantity + quantity > 2147483647:
            raise ValidationError("Превышено допустимое количество акций.")
        portfolio.cash -= amount
        position.quantity += quantity
        position.cost_basis = money_value(position.cost_basis + amount)
    else:
        if quantity > position.quantity:
            raise ValidationError("Недостаточно акций для продажи.")
        released = (
            position.cost_basis
            if quantity == position.quantity
            else rounded(position.cost_basis * quantity / position.quantity)
        )
        position.quantity -= quantity
        position.cost_basis -= released
        portfolio.cash = money_value(portfolio.cash + amount)
        realized = amount - released
    portfolio.save(update_fields=["cash"])
    position.save(update_fields=["quantity", "cost_basis"])
    trade = Trade.objects.create(
        portfolio=portfolio,
        share=share,
        side=side,
        quantity=quantity,
        price=price,
        amount=amount,
        realized_pnl=realized,
        request_id=request_id,
        strategy=strategy,
        automated=strategy is not None,
    )
    return trade, True


def portfolio_summary(portfolio):
    holdings, market_total, cost_total = [], Decimal(0), Decimal(0)
    complete = True
    for position in (
        portfolio.positions.filter(quantity__gt=0)
        .select_related("share")
        .order_by("share__name", "pk")
    ):
        share = position.share
        comparable = (
            share.last_price is not None
            and share.currency.lower() == portfolio.currency.lower()
        )
        value = rounded(share.last_price * position.quantity) if comparable else None
        complete = complete and comparable
        if value is not None:
            market_total += value
        cost_total += position.cost_basis
        holdings.append(
            {
                "share": share,
                "quantity": position.quantity,
                "average_price": position.average_price,
                "cost_basis": position.cost_basis,
                "market_value": value,
                "unrealized_pnl": (
                    value - position.cost_basis if value is not None else None
                ),
            }
        )
    realized = rounded(
        portfolio.trades.aggregate(total=Sum("realized_pnl", default=Decimal(0)))[
            "total"
        ]
    )
    value = portfolio.cash + market_total if complete else None
    profit = value - portfolio.initial_cash if complete else None
    return {
        "holdings": holdings,
        "cash": portfolio.cash,
        "complete": complete,
        "market_value": market_total if complete else None,
        "total_value": value,
        "realized_pnl": realized,
        "unrealized_pnl": market_total - cost_total if complete else None,
        "total_pnl": profit,
        "return_percent": percent(profit, portfolio.initial_cash) if complete else None,
    }
