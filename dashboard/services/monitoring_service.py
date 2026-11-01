from decimal import Decimal
import logging
from typing import List

from dashboard.models import PriceNotification, Share, WatchlistItem

logger = logging.getLogger("main")


def check_watchlist_alerts(shares: List[Share]) -> int:
    """
    Проверяет целевые ценовые уровни для обновленных акций.
    Исключает дублирование уведомлений:
    - При достижении условия уведомление генерируется один раз и выставляется is_triggered=True.
    - Флаг сбрасывается только когда цена возвращается обратно за пороговый уровень.
    """
    notifications_created = 0

    for share in shares:
        if share.last_price is None:
            continue

        active_items = WatchlistItem.objects.filter(share=share, is_active=True)
        for item in active_items:
            current_price = share.last_price
            target_price = item.target_price

            is_condition_met = False
            if item.condition == "ABOVE" and current_price >= target_price:
                is_condition_met = True
            elif item.condition == "BELOW" and current_price <= target_price:
                is_condition_met = True

            if is_condition_met:
                if not item.is_triggered:
                    # Условие выполнено впервые для этого уровня: создаем уведомление
                    msg_direction = "достигла или превысила" if item.condition == "ABOVE" else "опустилась ниже или достигла"
                    message = (
                        f"Акция {share.ticker} ({share.name}) {msg_direction} "
                        f"целевого уровня {target_price} {share.currency}! "
                        f"Текущая цена: {current_price} {share.currency}."
                    )
                    PriceNotification.objects.create(
                        user=item.user,
                        share=share,
                        target_price=target_price,
                        actual_price=current_price,
                        message=message,
                    )
                    item.is_triggered = True
                    item.save(update_fields=["is_triggered", "updated_at"])
                    notifications_created += 1
                    logger.info(f"Создано уведомление для {item.user.email} по акции {share.ticker}")
            else:
                # Цена вернулась обратно — сбрасываем флаг для возможности повторного срабатывания в будущем
                if item.is_triggered:
                    item.is_triggered = False
                    item.save(update_fields=["is_triggered", "updated_at"])

    return notifications_created
