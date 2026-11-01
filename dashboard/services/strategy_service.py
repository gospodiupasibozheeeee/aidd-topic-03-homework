from decimal import Decimal
import logging
from typing import Dict, List, Optional, Tuple

from dashboard.models import (
    PortfolioPosition,
    PortfolioTransaction,
    Share,
    StrategyExecutionLog,
    TradingStrategy,
)
from dashboard.services.portfolio_service import buy_share, sell_share

logger = logging.getLogger("main")


def execute_strategy(
    strategy: TradingStrategy, current_price: Optional[Decimal] = None
) -> Tuple[bool, str]:
    """
    Выполняет один шаг оценки и симуляции стратегии:
    - Проверяет активность стратегии
    - Проверяет соответствие текущей цены заданным условиям (пороговым или процентным)
    - Автоматически инициирует сделку покупки или продажи
    - Ведет журнал исполнения в StrategyExecutionLog
    """
    if not strategy.is_active:
        return False, "Стратегия не активна"

    price = current_price or strategy.share.last_price
    if price is None or price <= Decimal("0.00"):
        return False, "Нет актуальной цены инструмента"

    portfolio = strategy.portfolio
    share = strategy.share
    qty = strategy.trade_quantity

    action_taken = False
    status_message = "Условия стратегии не выполнены"

    if strategy.strategy_type == "THRESHOLD_BUY_SELL":
        # Покупка при падении цены до/ниже buy_threshold
        if price <= strategy.buy_threshold:
            tx, err = buy_share(
                portfolio=portfolio,
                share=share,
                quantity=qty,
                price=price,
                strategy=strategy,
            )
            if tx:
                msg = f"Покупка {qty} шт. по {price} {share.currency} (порог <= {strategy.buy_threshold})"
                StrategyExecutionLog.objects.create(
                    strategy=strategy,
                    action="BUY",
                    price=price,
                    quantity=qty,
                    message=msg,
                )
                logger.info(f"[Стратегия {strategy.name}] {msg}")
                return True, msg
            else:
                msg = f"Сигнал на покупку по {price} {share.currency}, но операция отклонена: {err}"
                StrategyExecutionLog.objects.create(
                    strategy=strategy,
                    action="SKIP",
                    price=price,
                    quantity=qty,
                    message=msg,
                )
                return False, msg

        # Продажа при росте цены до/выше sell_threshold
        elif price >= strategy.sell_threshold:
            tx, err = sell_share(
                portfolio=portfolio,
                share=share,
                quantity=qty,
                price=price,
                strategy=strategy,
            )
            if tx:
                msg = f"Продажа {qty} шт. по {price} {share.currency} (порог >= {strategy.sell_threshold}), PnL: {tx.realized_pnl}"
                StrategyExecutionLog.objects.create(
                    strategy=strategy,
                    action="SELL",
                    price=price,
                    quantity=qty,
                    message=msg,
                )
                logger.info(f"[Стратегия {strategy.name}] {msg}")
                return True, msg
            else:
                msg = f"Сигнал на продажу по {price} {share.currency}, но операция отклонена: {err}"
                StrategyExecutionLog.objects.create(
                    strategy=strategy,
                    action="SKIP",
                    price=price,
                    quantity=qty,
                    message=msg,
                )
                return False, msg

    elif strategy.strategy_type == "DIP_BUY_PROFIT_SELL":
        # Процентная стратегия: buy_threshold = % просадки, sell_threshold = % прибыли
        position = PortfolioPosition.objects.filter(portfolio=portfolio, share=share).first()

        if position and position.quantity > 0 and position.average_buy_price > Decimal("0.00"):
            pct_diff = ((price - position.average_buy_price) / position.average_buy_price) * Decimal("100.00")

            # Фиксация прибыли
            if pct_diff >= strategy.sell_threshold:
                sell_qty = min(qty, position.quantity)
                tx, err = sell_share(
                    portfolio=portfolio,
                    share=share,
                    quantity=sell_qty,
                    price=price,
                    strategy=strategy,
                )
                if tx:
                    msg = f"Фиксация прибыли: продажа {sell_qty} шт. по {price} (доходность +{pct_diff:.2f}%), PnL: {tx.realized_pnl}"
                    StrategyExecutionLog.objects.create(
                        strategy=strategy,
                        action="SELL",
                        price=price,
                        quantity=sell_qty,
                        message=msg,
                    )
                    return True, msg
                else:
                    msg = f"Сигнал на продажу (+{pct_diff:.2f}%), но операция не удалась: {err}"
                    StrategyExecutionLog.objects.create(
                        strategy=strategy,
                        action="SKIP",
                        price=price,
                        quantity=sell_qty,
                        message=msg,
                    )
                    return False, msg

            # Докупка на просадке
            elif pct_diff <= -abs(strategy.buy_threshold):
                tx, err = buy_share(
                    portfolio=portfolio,
                    share=share,
                    quantity=qty,
                    price=price,
                    strategy=strategy,
                )
                if tx:
                    msg = f"Усреднение на просадке ({pct_diff:.2f}%): покупка {qty} шт. по {price}"
                    StrategyExecutionLog.objects.create(
                        strategy=strategy,
                        action="BUY",
                        price=price,
                        quantity=qty,
                        message=msg,
                    )
                    return True, msg
                else:
                    msg = f"Сигнал на докупку ({pct_diff:.2f}%), но отклонено: {err}"
                    StrategyExecutionLog.objects.create(
                        strategy=strategy,
                        action="SKIP",
                        price=price,
                        quantity=qty,
                        message=msg,
                    )
                    return False, msg
        else:
            # Позиции еще нет — совершаем начальную покупку по текущей цене
            tx, err = buy_share(
                portfolio=portfolio,
                share=share,
                quantity=qty,
                price=price,
                strategy=strategy,
            )
            if tx:
                msg = f"Инициализация позиции по стратегии: покупка {qty} шт. по {price} {share.currency}"
                StrategyExecutionLog.objects.create(
                    strategy=strategy,
                    action="BUY",
                    price=price,
                    quantity=qty,
                    message=msg,
                )
                return True, msg

    return False, status_message


def simulate_active_strategies(shares: Optional[List[Share]] = None) -> int:
    """
    Запускает проверку всех активных стратегий.
    Вызывается при обновлении котировок или по требованию.
    """
    strategies = TradingStrategy.objects.filter(is_active=True).select_related(
        "portfolio", "share", "user"
    )
    if shares is not None:
        share_ids = [s.id for s in shares]
        strategies = strategies.filter(share_id__in=share_ids)

    executed_count = 0
    for strat in strategies:
        try:
            executed, _ = execute_strategy(strat)
            if executed:
                executed_count += 1
        except Exception as e:
            logger.error(f"Ошибка при симуляции стратегии {strat.id} ({strat.name}): {e}")

    return executed_count


def get_strategy_performance(strategy: TradingStrategy) -> Dict:
    """
    Рассчитывает метрики эффективности инвестиционной стратегии:
    - Общее количество сделок
    - Реализованный PnL
    - Текущая позиция и рыночная оценка
    """
    transactions = PortfolioTransaction.objects.filter(strategy=strategy)
    buy_count = transactions.filter(transaction_type="BUY").count()
    sell_count = transactions.filter(transaction_type="SELL").count()

    realized_pnl = Decimal("0.00")
    for tx in transactions.filter(transaction_type="SELL"):
        realized_pnl += tx.realized_pnl

    position = PortfolioPosition.objects.filter(
        portfolio=strategy.portfolio, share=strategy.share
    ).first()

    return {
        "strategy": strategy,
        "total_trades": buy_count + sell_count,
        "buy_trades": buy_count,
        "sell_trades": sell_count,
        "realized_pnl": realized_pnl,
        "current_position_quantity": position.quantity if position else 0,
        "current_position_value": position.current_value if position else Decimal("0.00"),
    }
