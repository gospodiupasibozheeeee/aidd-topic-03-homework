from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

import plotly.graph_objects as go
from django.utils import timezone
from plotly.offline import plot

from investments.models import PriceSnapshot

PERIODS = {7: "7 дней", 30: "30 дней", 90: "90 дней", 180: "180 дней", 365: "365 дней"}
DEFAULT_PERIOD = 30


@dataclass(frozen=True)
class HistorySummary:
    first_price: Decimal | None
    last_price: Decimal | None
    absolute_change: Decimal
    percent_change: Decimal
    minimum: Decimal | None
    maximum: Decimal | None
    points: int


def _decimal(value) -> Decimal:
    return Decimal(str(value))


def record_snapshot(
    share,
    price,
    captured_at: datetime | None = None,
    source: str = "market",
) -> PriceSnapshot | None:
    """Persist a price snapshot, ignoring invalid/negative values."""

    if price is None:
        return None
    price = _decimal(price)
    if price <= 0:
        return None

    captured_at = captured_at or timezone.now()
    if timezone.is_naive(captured_at):
        captured_at = timezone.make_aware(captured_at, timezone.utc)

    snapshot, _ = PriceSnapshot.objects.get_or_create(
        share=share,
        captured_at=captured_at,
        defaults={"price": price, "source": source},
    )
    return snapshot


def get_history(share, days: int = DEFAULT_PERIOD):
    days = days if days in PERIODS else DEFAULT_PERIOD
    start = timezone.now() - timedelta(days=days)
    return list(
        PriceSnapshot.objects.filter(
            share=share,
            captured_at__gte=start,
        ).order_by("captured_at")
    )


def summarize(snapshots) -> HistorySummary:
    if not snapshots:
        return HistorySummary(
            first_price=None,
            last_price=None,
            absolute_change=Decimal("0"),
            percent_change=Decimal("0"),
            minimum=None,
            maximum=None,
            points=0,
        )

    prices = [_decimal(snapshot.price) for snapshot in snapshots]
    first_price = prices[0]
    last_price = prices[-1]
    absolute_change = last_price - first_price
    percent_change = (
        absolute_change / first_price * Decimal("100")
        if first_price != 0
        else Decimal("0")
    )
    return HistorySummary(
        first_price=first_price,
        last_price=last_price,
        absolute_change=absolute_change,
        percent_change=percent_change,
        minimum=min(prices),
        maximum=max(prices),
        points=len(prices),
    )


def build_chart(share, snapshots) -> str:
    if not snapshots:
        return ""

    x_data = [snapshot.captured_at for snapshot in snapshots]
    y_data = [float(snapshot.price) for snapshot in snapshots]

    figure = go.Figure(
        data=[
            go.Scatter(
                x=x_data,
                y=y_data,
                mode="lines+markers",
                name=share.ticker,
                line={"color": "#0d6efd", "width": 2},
                marker={"size": 4},
                hovertemplate="%{x|%d.%m.%Y %H:%M}<br>%{y:.2f}<extra></extra>",
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


def history_context(share, days: int = DEFAULT_PERIOD) -> dict:
    days = days if days in PERIODS else DEFAULT_PERIOD
    snapshots = get_history(share, days)
    return {
        "share": share,
        "period": days,
        "periods": PERIODS,
        "snapshots": snapshots,
        "summary": summarize(snapshots),
        "chart": build_chart(share, snapshots),
    }
