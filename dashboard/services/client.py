import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

import requests
from django.conf import settings

logger = logging.getLogger("main")


def parse_quotation(obj: Optional[Dict[str, Any]]) -> Optional[Decimal]:
    """Преобразует структуру units/nano в Decimal с полной точностью."""
    if not obj:
        return None
    units = int(obj.get("units", 0))
    nano = int(obj.get("nano", 0))
    return Decimal(units) + (Decimal(nano) / Decimal(10**9))


class TinkoffClient:
    """
    Клиент к REST API Т-Банк (Тинькофф) Инвестиций (OpenAPI v2).
    Поддерживает работу через HTTPS REST эндпоинты без зависимости от устаревшего gRPC.
    """

    def __init__(self, token: Optional[str] = None, base_url: Optional[str] = None, timeout: Optional[float] = None):
        self.token = token if token is not None else getattr(settings, "TINKOFF_TOKEN", "")
        self.base_url = (base_url or getattr(settings, "TINKOFF_API_URL", "https://invest-public-api.tbank.ru/rest")).rstrip("/")
        self.timeout = timeout or getattr(settings, "TINKOFF_TIMEOUT", 10.0)
        self.session = requests.Session()
        if self.token:
            self.session.headers.update({
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            })

    def _post(self, endpoint: str, json_data: dict) -> dict:
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        response = self.session.post(url, json=json_data, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def get_shares(self) -> List[Dict[str, Any]]:
        """Запрос каталога доступных акций."""
        if not self.token:
            logger.warning("TINKOFF_TOKEN не установлен, запрос каталога акций пропущен")
            return []

        try:
            data = self._post(
                "tinkoff.public.invest.api.v1.InstrumentsService/Shares",
                {"instrumentStatus": "INSTRUMENT_STATUS_BASE"},
            )
            return data.get("instruments", [])
        except Exception as e:
            logger.error(f"Ошибка при получении списка акций из Tinkoff API: {e}")
            return []

    def get_last_prices(self, figis: List[str]) -> Dict[str, Dict[str, Any]]:
        """
        Пакетный запрос последних цен по списку FIGI.
        Возвращает словарь {figi: {"price": Decimal, "time": datetime}}.
        """
        if not self.token or not figis:
            return {}

        try:
            data = self._post(
                "tinkoff.public.invest.api.v1.MarketDataService/GetLastPrices",
                {"figi": figis},
            )
            result = {}
            for item in data.get("lastPrices", []):
                figi = item.get("figi")
                price = parse_quotation(item.get("price"))
                raw_time = item.get("time")
                dt = None
                if raw_time:
                    try:
                        dt = datetime.fromisoformat(raw_time.replace("Z", "+00:00"))
                    except Exception:
                        dt = datetime.now(timezone.utc)
                if figi and price is not None:
                    result[figi] = {"price": price, "time": dt or datetime.now(timezone.utc)}
            return result
        except Exception as e:
            logger.error(f"Ошибка при пакетном получении цен из Tinkoff API: {e}")
            return {}

    def get_candles(self, figi: str, days: int = 180) -> List[Dict[str, Any]]:
        """Запрос дневных свечей по FIGI за указанное число дней."""
        if not self.token:
            return []

        now_dt = datetime.now(timezone.utc)
        from_dt = now_dt - timedelta(days=days)

        try:
            data = self._post(
                "tinkoff.public.invest.api.v1.MarketDataService/GetCandles",
                {
                    "figi": figi,
                    "from": from_dt.isoformat(),
                    "to": now_dt.isoformat(),
                    "interval": "CANDLE_INTERVAL_DAY",
                },
            )
            candles = []
            for item in data.get("candles", []):
                close_price = parse_quotation(item.get("close"))
                raw_time = item.get("time")
                if close_price is not None and raw_time:
                    try:
                        date_val = datetime.fromisoformat(raw_time.replace("Z", "+00:00")).date()
                    except Exception:
                        continue
                    candles.append({"date": date_val, "close": close_price})
            return candles
        except Exception as e:
            logger.error(f"Ошибка при получении свечей для {figi}: {e}")
            return []
