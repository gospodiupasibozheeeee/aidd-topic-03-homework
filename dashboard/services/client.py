"""Read-only client for the documented T-Invest REST gateway."""

from decimal import Decimal, InvalidOperation

import requests
from django.conf import settings
from django.utils import timezone
from django.utils.dateparse import parse_datetime


class MarketDataError(Exception):
    """Market data is unavailable or a provider response is invalid."""


def quotation_to_decimal(value):
    try:
        price = Decimal(value["units"]) + Decimal(value.get("nano", 0)) / 10**9
        if not price.is_finite() or abs(price) >= Decimal(10) ** 15:
            raise ValueError("Price outside the supported database range")
        return price
    except (KeyError, TypeError, ValueError, InvalidOperation) as exc:
        raise MarketDataError("Invalid price in market response") from exc


def quotation_time(value):
    try:
        result = parse_datetime(value)
        if result is None or timezone.is_naive(result):
            raise ValueError("Expected timestamp with timezone")
        return result
    except (TypeError, ValueError) as exc:
        raise MarketDataError("Invalid time in market response") from exc


class MarketDataClient:
    def __enter__(self):
        self.session = requests.Session()
        return self

    def __exit__(self, *args):
        self.session.close()

    def _post(self, service, method, payload, field):
        if not settings.TINKOFF_TOKEN:
            raise MarketDataError("TINKOFF_TOKEN is not configured")
        url = (
            f"{settings.TINKOFF_API_URL.rstrip('/')}/"
            f"tinkoff.public.invest.api.contract.v1.{service}/{method}"
        )
        try:
            response = self.session.post(
                url,
                json=payload,
                headers={"Authorization": f"Bearer {settings.TINKOFF_TOKEN}"},
                timeout=settings.TINKOFF_TIMEOUT,
                verify=settings.TINKOFF_CA_BUNDLE or True,
            )
            response.raise_for_status()
            data = response.json()
        except (requests.RequestException, ValueError) as exc:
            # Never log credentials, request headers, or provider response bodies.
            raise MarketDataError("T-Invest request failed") from exc
        if not isinstance(data, dict) or not isinstance(data.get(field), list):
            raise MarketDataError(f"Missing {field} in market response")
        return data[field]

    def shares(self):
        return self._post(
            "InstrumentsService",
            "Shares",
            {"instrumentStatus": "INSTRUMENT_STATUS_BASE"},
            "instruments",
        )

    def last_prices(self, figis):
        return self._post(
            "MarketDataService", "GetLastPrices", {"instrumentId": figis}, "lastPrices"
        )

    def candles(self, figi, start, end):
        return self._post(
            "MarketDataService",
            "GetCandles",
            {
                "instrumentId": figi,
                "from": start.isoformat(),
                "to": end.isoformat(),
                "interval": "CANDLE_INTERVAL_DAY",
            },
            "candles",
        )
