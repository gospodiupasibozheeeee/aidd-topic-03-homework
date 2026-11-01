from datetime import timedelta

from django.utils import timezone
from plotly.graph_objs import Scatter
from plotly.offline import plot

from .client import (
    MarketDataClient,
    MarketDataError,
    quotation_time,
    quotation_to_decimal,
)


def get_graph(share):
    end = timezone.now()
    with MarketDataClient() as client:
        candles = client.candles(share.figi, end - timedelta(days=180), end)
    if not candles:
        return ""
    try:
        points = sorted(
            (quotation_time(candle["time"]), quotation_to_decimal(candle["close"]))
            for candle in candles
        )
    except (KeyError, TypeError) as exc:
        raise MarketDataError("Incomplete candle") from exc
    return plot(
        [
            Scatter(
                x=[p[0] for p in points],
                y=[p[1] for p in points],
                mode="lines",
                name=share.ticker,
            )
        ],
        output_type="div",
        include_plotlyjs=True,
        auto_open=False,
    )
