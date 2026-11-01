from datetime import timedelta
from decimal import Decimal
import logging
from typing import Any, Dict, Optional

from django.db.models import Max, Min
from django.utils import timezone
import plotly.graph_objs as go
import plotly.offline as opy

from dashboard.models import PriceHistory, Share

logger = logging.getLogger("main")


def record_price(
    share: Share, price: Decimal, recorded_at: Optional[Any] = None
) -> Optional[PriceHistory]:
    """
    Сохраняет рыночную цену акции в историю (PriceHistory).
    Исключает дублирование записи, если последняя зафиксированная цена совпадает по времени.
    """
    if price is None:
        return None

    at_time = recorded_at or timezone.now()

    # Избегаем создания точной копии за последнюю минуту с той же ценой
    last_rec = PriceHistory.objects.filter(share=share).first()
    if (
        last_rec
        and last_rec.price == price
        and (at_time - last_rec.recorded_at).total_seconds() < 60
    ):
        return last_rec

    return PriceHistory.objects.create(
        share=share,
        price=price,
        recorded_at=at_time,
    )


def _get_period_cutoff(period: str):
    now = timezone.now()
    period = period.upper()
    if period == "1D":
        return now - timedelta(days=1)
    elif period == "1W":
        return now - timedelta(days=7)
    elif period == "1M":
        return now - timedelta(days=30)
    elif period == "1Y":
        return now - timedelta(days=365)
    return None  # ALL


def get_price_history(share: Share, period: str = "1M"):
    """Возвращает QuerySet истории цен за указанный период (1D, 1W, 1M, 1Y, ALL)"""
    cutoff = _get_period_cutoff(period)
    qs = PriceHistory.objects.filter(share=share)
    if cutoff:
        qs = qs.filter(recorded_at__gte=cutoff)
    return qs.order_by("recorded_at")


def calculate_price_dynamics(share: Share, period: str = "1M") -> Dict[str, Any]:
    """
    Анализирует динамику рыночной цены акции:
    - Начальная и конечная цена за период
    - Абсолютное и процентное изменение
    - Минимум и максимум за период
    """
    history = list(get_price_history(share, period))
    if not history:
        current_price = share.last_price or Decimal("0.00")
        return {
            "period": period,
            "data_points": 0,
            "start_price": current_price,
            "end_price": current_price,
            "min_price": current_price,
            "max_price": current_price,
            "absolute_change": Decimal("0.00"),
            "percentage_change": Decimal("0.00"),
            "is_growth": True,
        }

    start_price = history[0].price
    end_price = history[-1].price
    prices = [h.price for h in history]
    min_price = min(prices)
    max_price = max(prices)

    absolute_change = end_price - start_price
    percentage_change = (
        ((absolute_change / start_price) * Decimal("100.00")).quantize(Decimal("0.01"))
        if start_price > Decimal("0.00")
        else Decimal("0.00")
    )

    return {
        "period": period,
        "data_points": len(history),
        "start_price": start_price,
        "end_price": end_price,
        "min_price": min_price,
        "max_price": max_price,
        "absolute_change": absolute_change.quantize(Decimal("0.01")),
        "percentage_change": percentage_change,
        "is_growth": absolute_change >= Decimal("0.00"),
    }


def generate_history_chart(share: Share, period: str = "1M") -> str:
    """
    Строит интерактивный график изменения цены акции на основе накопленной истории PriceHistory.
    """
    history = list(get_price_history(share, period))
    if not history:
        # Если в PriceHistory пока нет записей, но есть текущая цена
        if share.last_price is not None:
            now = timezone.now()
            x_vals = [now - timedelta(minutes=5), now]
            y_vals = [float(share.last_price), float(share.last_price)]
        else:
            return "<div class='alert alert-info'>История котировок пока пуста. Данные накапливаются при обновлении цен.</div>"
    else:
        x_vals = [h.recorded_at for h in history]
        y_vals = [float(h.price) for h in history]

    line_color = "#28a745" if y_vals[-1] >= y_vals[0] else "#dc3545"

    trace = go.Scatter(
        x=x_vals,
        y=y_vals,
        mode="lines+markers",
        name=f"Цена ({share.currency})",
        line=dict(color=line_color, width=2.5),
        marker=dict(size=4),
        fill="tozeroy",
        fillcolor="rgba(40, 167, 69, 0.1)" if y_vals[-1] >= y_vals[0] else "rgba(220, 53, 69, 0.1)",
    )

    layout = go.Layout(
        title=f"История котировок {share.ticker} ({share.name}) — Период: {period}",
        xaxis=dict(title="Время", showgrid=True),
        yaxis=dict(title=f"Цена ({share.currency})", showgrid=True),
        margin=dict(l=40, r=40, t=50, b=40),
        height=400,
        hovermode="x unified",
        template="plotly_white",
    )

    fig = go.Figure(data=[trace], layout=layout)
    return opy.plot(fig, auto_open=False, output_type="div")
