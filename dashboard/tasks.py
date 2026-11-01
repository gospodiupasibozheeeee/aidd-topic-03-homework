import logging
from django.utils import timezone

from config.celery import app
from dashboard.models import Share
from dashboard.services.client import TinkoffClient
from dashboard.services.market_data import get_batch_market_data, get_last_data

logger = logging.getLogger("main")


@app.task
def update_last_price():
    """
    Фоновая задача периодического обновления текущих рыночных цен акций.
    Использует пакетный запрос котировок для исключения проблемы N+1 сетевых запросов.
    """
    shares = list(Share.objects.all())
    if not shares:
        return

    client = TinkoffClient()
    updated_count = 0
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

            # Обновляем поля модели, включая updated_at
            Share.objects.filter(id=share.id).update(
                last_price=last_price,
                is_trend_high=is_trend_high,
                updated_at=now_dt,
            )
            updated_count += 1
        except Exception as e:
            logger.error(f"Ошибка при обновлении цены для {share.ticker}: {e}")

    logger.info(f"Фоновое обновление цен завершено. Обновлено инструментов: {updated_count}")
