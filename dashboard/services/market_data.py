import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

from dashboard.models import Share
from dashboard.services.client import TinkoffClient

logger = logging.getLogger("main")


def get_last_data(share: Share, client: Optional[TinkoffClient] = None) -> Optional[Tuple[Decimal, datetime]]:
    """
    Получение последней цены и временной метки для одной акции.
    Возвращает (price, time) или None при недоступности данных.
    """
    client = client or TinkoffClient()
    prices = client.get_last_prices([share.figi])
    data = prices.get(share.figi)
    if data:
        logger.info(f"Получены котировки для акции {share.ticker} (id={share.id}): {data['price']}")
        return data["price"], data["time"]
    return None


def get_batch_market_data(shares: List[Share], client: Optional[TinkoffClient] = None) -> Dict[int, Tuple[Decimal, datetime]]:
    """
    Пакетное получение актуальных цен для списка акций за один сетевой запрос.
    Возвращает словарь {share_id: (price, time)}.
    """
    if not shares:
        return {}

    client = client or TinkoffClient()
    figi_to_share = {share.figi: share for share in shares if share.figi}
    prices = client.get_last_prices(list(figi_to_share.keys()))

    result = {}
    for figi, data in prices.items():
        share = figi_to_share.get(figi)
        if share:
            result[share.id] = (data["price"], data["time"])
    return result
