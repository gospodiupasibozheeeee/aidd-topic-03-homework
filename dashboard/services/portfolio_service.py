from decimal import Decimal
from typing import Optional, Tuple

from django.db import transaction

from dashboard.models import (
    Portfolio,
    PortfolioPosition,
    PortfolioTransaction,
    Share,
    TradingStrategy,
)


def get_or_create_portfolio(user) -> Portfolio:
    """Возвращает существующий портфель пользователя или создает основной."""
    portfolio = Portfolio.objects.filter(user=user).first()
    if not portfolio:
        portfolio = Portfolio.objects.create(
            user=user,
            name="Основной портфель",
            balance=Decimal("100000.00"),
            initial_balance=Decimal("100000.00"),
            currency="USD",
        )
    return portfolio


@transaction.atomic
def buy_share(
    portfolio: Portfolio,
    share: Share,
    quantity: int,
    price: Optional[Decimal] = None,
    strategy: Optional[TradingStrategy] = None,
) -> Tuple[Optional[PortfolioTransaction], Optional[str]]:
    """
    Моделирует операцию покупки акций:
    - Проверяет баланс
    - Списывает сумму покупки
    - Рассчитывает средневзвешенную цену покупки
    - Создает запись транзакции
    """
    if quantity <= 0:
        return None, "Количество акций для покупки должно быть больше 0"

    execution_price = price if price is not None else share.last_price
    if execution_price is None or execution_price <= Decimal("0.00"):
        return None, "Не установлена рыночная цена для совершения сделки"

    total_amount = Decimal(quantity) * execution_price

    # Блокируем строку портфеля для атомарного списания
    portfolio = Portfolio.objects.select_for_update().get(id=portfolio.id)
    if portfolio.balance < total_amount:
        return (
            None,
            f"Недостаточно средств на балансе. Требуется {total_amount} {portfolio.currency}, доступно {portfolio.balance} {portfolio.currency}",
        )

    # Списываем средства
    portfolio.balance -= total_amount
    portfolio.save(update_fields=["balance"])

    # Обновляем позицию портфеля
    position, created = PortfolioPosition.objects.select_for_update().get_or_create(
        portfolio=portfolio,
        share=share,
        defaults={"quantity": 0, "average_buy_price": Decimal("0.00")},
    )

    old_total_cost = Decimal(position.quantity) * position.average_buy_price
    new_quantity = position.quantity + quantity
    new_average_price = (old_total_cost + total_amount) / Decimal(new_quantity)

    position.quantity = new_quantity
    position.average_buy_price = new_average_price.quantize(Decimal("0.01"))
    position.save()

    # Фиксируем сделку
    tx = PortfolioTransaction.objects.create(
        portfolio=portfolio,
        share=share,
        strategy=strategy,
        transaction_type="BUY",
        quantity=quantity,
        price=execution_price,
        total_amount=total_amount,
        realized_pnl=Decimal("0.00"),
    )
    return tx, None


@transaction.atomic
def sell_share(
    portfolio: Portfolio,
    share: Share,
    quantity: int,
    price: Optional[Decimal] = None,
    strategy: Optional[TradingStrategy] = None,
) -> Tuple[Optional[PortfolioTransaction], Optional[str]]:
    """
    Моделирует операцию продажи акций:
    - Проверяет наличие нужного объема в позиции
    - Рассчитывает реализованный PnL
    - Зачисляет средства на баланс
    - Уменьшает позицию
    - Создает запись транзакции
    """
    if quantity <= 0:
        return None, "Количество акций для продажи должно быть больше 0"

    execution_price = price if price is not None else share.last_price
    if execution_price is None or execution_price <= Decimal("0.00"):
        return None, "Не установлена рыночная цена для совершения сделки"

    total_amount = Decimal(quantity) * execution_price

    try:
        position = PortfolioPosition.objects.select_for_update().get(
            portfolio=portfolio, share=share
        )
    except PortfolioPosition.DoesNotExist:
        return None, f"В портфеле нет акций {share.ticker} для продажи"

    if position.quantity < quantity:
        return (
            None,
            f"Недостаточно акций для продажи. Во владении: {position.quantity}, запрошено: {quantity}",
        )

    # Расчет реализованной прибыли/убытка
    realized_pnl = (execution_price - position.average_buy_price) * Decimal(quantity)

    # Зачисление выручки на баланс
    portfolio = Portfolio.objects.select_for_update().get(id=portfolio.id)
    portfolio.balance += total_amount
    portfolio.save(update_fields=["balance"])

    # Обновление позиции
    position.quantity -= quantity
    if position.quantity == 0:
        position.delete()
    else:
        position.save(update_fields=["quantity"])

    # Фиксация сделки
    tx = PortfolioTransaction.objects.create(
        portfolio=portfolio,
        share=share,
        strategy=strategy,
        transaction_type="SELL",
        quantity=quantity,
        price=execution_price,
        total_amount=total_amount,
        realized_pnl=realized_pnl.quantize(Decimal("0.01")),
    )
    return tx, None

