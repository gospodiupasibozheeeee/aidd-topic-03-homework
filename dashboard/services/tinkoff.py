"""Tinkoff Invest API adapter.

The SDK is imported lazily so that the application can start without the
optional ``tinkoff-investments`` package (for example on Python versions for
which the SDK has no wheel). All failures are reported as ``MarketDataError``
so views can degrade gracefully instead of returning HTTP 500.
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Iterable, Iterator

from django.conf import settings

logger = logging.getLogger("dashboard")


class MarketDataError(Exception):
    """Raised when market data cannot be obtained from the external API."""


def _load_client_class():
    try:
        from tinkoff.invest import Client
    except ImportError as exc:  # pragma: no cover - depends on optional extra
        raise MarketDataError(
            "Tinkoff Invest SDK не установлен. Установите пакет "
            "tinkoff-investments или работайте без рыночных данных."
        ) from exc
    return Client


def _load_candle_api():
    try:
        from tinkoff.invest import CandleInterval
        from tinkoff.invest.utils import now
    except ImportError as exc:  # pragma: no cover - depends on optional extra
        raise MarketDataError(
            "Tinkoff Invest SDK не установлен: график недоступен."
        ) from exc
    return CandleInterval, now


def quotation_to_decimal(value) -> Decimal:
    """Convert a Tinkoff Quotation/MoneyValue (units + nano) to Decimal."""

    if value is None:
        raise MarketDataError("Tinkoff API вернул пустое значение цены")

    units = getattr(value, "units", None)
    nano = getattr(value, "nano", None)
    if units is not None or nano is not None:
        try:
            return Decimal(int(units or 0)) + Decimal(int(nano or 0)) / Decimal(
                "1000000000"
            )
        except (TypeError, ValueError, InvalidOperation) as exc:
            raise MarketDataError(f"Некорректная цена Tinkoff: {value!r}") from exc

    try:
        return Decimal(str(value))
    except (TypeError, ValueError, InvalidOperation) as exc:
        raise MarketDataError(f"Некорректная цена Tinkoff: {value!r}") from exc


@contextmanager
def tinkoff_client() -> Iterator[object]:
    """Yield an authenticated Tinkoff client and translate SDK errors."""

    if not settings.TINKOFF_TOKEN:
        raise MarketDataError(
            "TINKOFF_TOKEN не задан. Укажите токен в .env, чтобы получать "
            "рыночные данные."
        )

    client_class = _load_client_class()
    try:
        with client_class(settings.TINKOFF_TOKEN) as client:
            yield client
    except MarketDataError:
        raise
    except Exception as exc:  # pragma: no cover - network/SDK failure
        logger.exception("Tinkoff API request failed")
        raise MarketDataError(f"Ошибка Tinkoff Invest API: {exc}") from exc


def get_last_prices(shares: Iterable[object]) -> dict[str, tuple[Decimal, datetime]]:
    """Return {figi: (price, time)} for all requested shares in one call."""

    figis = list(
        dict.fromkeys(share.figi for share in shares if getattr(share, "figi", None))
    )
    if not figis:
        return {}

    with tinkoff_client() as client:
        response = client.market_data.get_last_prices(figi=figis)
        result: dict[str, tuple[Decimal, datetime]] = {}
        for item in response.last_prices:
            figi = getattr(item, "figi", None)
            if not figi:
                continue
            price_time = getattr(item, "time", None) or datetime.now(timezone.utc)
            result[figi] = (quotation_to_decimal(item.price), price_time)
        return result


def get_candles(share, days: int = 180) -> list[object]:
    """Return daily candles for the share for the last ``days`` days."""

    CandleInterval, now = _load_candle_api()
    start = now() - timedelta(days=days)
    with tinkoff_client() as client:
        return list(
            client.get_all_candles(
                figi=share.figi,
                from_=start,
                interval=CandleInterval.CANDLE_INTERVAL_DAY,
            )
        )
