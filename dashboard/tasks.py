import logging
from django.utils import timezone

from config.celery import app
from dashboard.models import Share
from dashboard.services.client import TinkoffClient
from dashboard.services.history_service import record_price
from dashboard.services.market_data import get_batch_market_data, get_last_data
from dashboard.services.monitoring_service import check_watchlist_alerts
from dashboard.services.strategy_service import simulate_active_strategies

logger = logging.getLogger("main")


@app.task
def update_last_price():
    """
    Фоновая задача периодического обновления текущих рыночных цен акций:
    - Обновляет текущие цены и тренды в Share
    - Автоматически сохраняет котировки в историю цен (PriceHistory)
    - Проверяет персональные уровни мониторинга и генерирует уведомления
    - Выполняет симуляцию активных торговых стратегий
    """
    shares = list(Share.objects.all())
    if not shares:
        return

    client = TinkoffClient()
    updated_shares = []
    now_dt = timezone.now()

    # Пытаемся получить котировки пакетом
    batch_data = get_batch_market_data(shares, client=client)

    for share in shares:
        try:
            if share.id in batch_data:
                last_price, quote_time = batch_data[share.id]
            else:
                data = get_last_data(share, client=client)
                if not data:
                    continue
                last_price, quote_time = data

            # Определение тренда
            if share.last_price is not None and share.last_price > last_price:
                is_trend_high = False
            else:
                is_trend_high = True

            # Обновляем поля модели
            Share.objects.filter(id=share.id).update(
                last_price=last_price,
                is_trend_high=is_trend_high,
                updated_at=now_dt,
            )

            # Сохраняем цену в историю (Задание 4.3)
            record_price(share=share, price=last_price, recorded_at=now_dt)

            # Обновляем объект в памяти для сервисов мониторинга и стратегий
            share.last_price = last_price
            share.is_trend_high = is_trend_high
            share.updated_at = now_dt
            updated_shares.append(share)
        except Exception as e:
            logger.error(f"Ошибка при обновлении цены для {share.ticker}: {e}")

    logger.info(f"Фоновое обновление цен завершено. Обновлено инструментов: {len(updated_shares)}")

    if updated_shares:
        # Проверка персональных уровней мониторинга (Задание 4.1)
        alerts_created = check_watchlist_alerts(updated_shares)
        if alerts_created > 0:
            logger.info(f"Сгенерировано уведомлений мониторинга: {alerts_created}")

        # Симуляция инвестиционных стратегий (Задание 4.4)
        simulated_deals = simulate_active_strategies(updated_shares)
        if simulated_deals > 0:
            logger.info(f"Исполнено виртуальных операций по стратегиям: {simulated_deals}")
