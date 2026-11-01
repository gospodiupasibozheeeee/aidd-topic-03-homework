from datetime import datetime, timedelta, timezone
from decimal import Decimal
import logging
from typing import Optional

from plotly.graph_objs import Scatter
from plotly.offline import plot

from dashboard.models import Share
from dashboard.services.client import TinkoffClient

logger = logging.getLogger("main")


def get_graph(share: Share, client: Optional[TinkoffClient] = None) -> str:
    """
    Построение графика котировок за последние 180 дней.
    Возвращает HTML-фрагмент (div) с графиком Plotly.
    """
    client = client or TinkoffClient()
    candles = client.get_candles(share.figi, days=180)

    x_data = []
    y_data = []

    if candles:
        for candle in candles:
            x_data.append(candle["date"])
            y_data.append(float(candle["close"]))
    elif share.last_price is not None:
        # При отсутствии внешнего API или токена строим базовый график от текущей цены
        today = datetime.now(timezone.utc).date()
        base_price = float(share.last_price)
        for i in range(180, -1, -5):
            x_data.append(today - timedelta(days=i))
            y_data.append(base_price)

    if not x_data:
        today = datetime.now(timezone.utc).date()
        x_data = [today - timedelta(days=1), today]
        y_data = [0.0, 0.0]

    line_color = "#28a745" if share.is_trend_high else "#dc3545"

    plot_div = plot(
        [
            Scatter(
                x=x_data,
                y=y_data,
                mode="lines",
                name=share.ticker,
                opacity=0.85,
                line=dict(color=line_color, width=2),
            )
        ],
        output_type="div",
        show_link=False,
        link_text="",
        include_plotlyjs=False,
    )
    return plot_div
