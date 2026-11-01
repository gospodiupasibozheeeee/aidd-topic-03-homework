from datetime import date, datetime, time, timedelta, timezone

from django.db.models import Avg
from django.db.models.functions import TruncDate
from plotly.graph_objs import Scatter
from plotly.offline import plot

from investing.models import PricePoint

from .trading import percent, rounded


def history_data(share, start, end):
    records = PricePoint.objects.filter(
        share=share,
        observed_at__gte=datetime.combine(start, time.min, tzinfo=timezone.utc),
    )
    if end < date.max:
        records = records.filter(
            observed_at__lt=datetime.combine(
                end + timedelta(days=1), time.min, tzinfo=timezone.utc
            )
        )
    first, last = records.first(), records.last()
    currencies = list(records.order_by().values_list("currency", flat=True).distinct())
    comparable = len(currencies) == 1
    change = last.price - first.price if first and comparable else None
    summary = {
        "count": records.count(),
        "first_price": first.price if first else None,
        "last_price": last.price if last else None,
        "absolute_change": change,
        "percent_change": percent(change, first.price) if comparable else None,
        "currencies": currencies,
        "comparable": comparable,
    }
    daily = list(
        records.order_by()
        .annotate(day=TruncDate("observed_at", tzinfo=timezone.utc))
        .values("day", "currency")
        .annotate(price=Avg("price"))
        .order_by("day", "currency")
    )
    for point in daily:
        point["price"] = rounded(point["price"])
    return records, summary, daily


def history_graph(daily):
    if not daily:
        return ""
    traces = []
    for currency in sorted({point["currency"] for point in daily}):
        points = [point for point in daily if point["currency"] == currency]
        traces.append(
            Scatter(
                x=[p["day"] for p in points],
                y=[p["price"] for p in points],
                mode="lines+markers",
                name=f"Средняя за день ({currency})",
            )
        )
    return plot(traces, output_type="div", include_plotlyjs=True, auto_open=False)
