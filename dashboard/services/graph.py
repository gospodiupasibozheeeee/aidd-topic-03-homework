from __future__ import annotations

import plotly.graph_objects as go
from plotly.offline import plot

from .tinkoff import MarketDataError, get_candles, quotation_to_decimal


def get_graph(share, days: int = 180) -> str:
    """Build a Plotly HTML fragment with daily closing prices.

    Only the chart container is generated; Plotly.js itself is loaded once in
    the page template (``include_plotlyjs=False``) to avoid a multi-megabyte
    inline script on every request.
    """

    candles = get_candles(share, days=days)
    if not candles:
        raise MarketDataError(
            f"Нет исторических данных для {share.ticker} за {days} дней."
        )

    x_data = [candle.time.date() for candle in candles]
    y_data = [float(quotation_to_decimal(candle.close)) for candle in candles]

    figure = go.Figure(
        data=[
            go.Scatter(
                x=x_data,
                y=y_data,
                mode="lines",
                name=share.ticker,
                line={"color": "#0d6efd", "width": 2},
                hovertemplate="%{x|%d.%m.%Y}<br>%{y:.2f}<extra></extra>",
            )
        ]
    )
    figure.update_layout(
        margin={"l": 40, "r": 20, "t": 20, "b": 40},
        paper_bgcolor="white",
        plot_bgcolor="white",
        showlegend=False,
        xaxis={"showgrid": True, "gridcolor": "#e9ecef"},
        yaxis={"showgrid": True, "gridcolor": "#e9ecef"},
    )

    return plot(
        figure,
        output_type="div",
        include_plotlyjs=False,
        show_link=False,
        config={"displayModeBar": False, "responsive": True},
    )
