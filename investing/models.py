import uuid
from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q

QUANTUM = Decimal("0.000000001")


def money(*args, **kwargs):
    return models.DecimalField(*args, max_digits=24, decimal_places=9, **kwargs)


class PricePoint(models.Model):
    share = models.ForeignKey(
        "dashboard.Share", on_delete=models.CASCADE, related_name="price_history"
    )
    observed_at = models.DateTimeField()
    currency = models.CharField(max_length=20)
    price = money(validators=[MinValueValidator(0)])

    class Meta:
        ordering = ("observed_at", "pk")
        constraints = [
            models.UniqueConstraint(
                fields=("share", "observed_at"), name="unique_share_observation"
            ),
            models.CheckConstraint(
                condition=Q(price__gte=0), name="nonnegative_observed_price"
            ),
        ]


class Watchlist(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="watchlists"
    )
    name = models.CharField("Название", max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("name", "pk")
        constraints = [
            models.UniqueConstraint(
                fields=("owner", "name"), name="unique_owner_watchlist"
            )
        ]

    def __str__(self):
        return self.name


class WatchItem(models.Model):
    class Direction(models.TextChoices):
        ABOVE = "gte", "Не ниже"
        BELOW = "lte", "Не выше"

    watchlist = models.ForeignKey(
        Watchlist, on_delete=models.CASCADE, related_name="items"
    )
    share = models.ForeignKey("dashboard.Share", on_delete=models.CASCADE)
    target = money("Целевая цена", null=True, blank=True)
    direction = models.CharField(
        "Условие", max_length=3, choices=Direction, default=Direction.ABOVE
    )
    revision = models.PositiveIntegerField(default=1, editable=False)
    triggered_at = models.DateTimeField(null=True, blank=True, editable=False)

    class Meta:
        ordering = ("pk",)
        constraints = [
            models.UniqueConstraint(
                fields=("watchlist", "share"), name="unique_watchlist_share"
            ),
            models.CheckConstraint(
                condition=Q(target__isnull=True) | Q(target__gt=0),
                name="positive_watch_target",
            ),
        ]

    def clean(self):
        if self.target is not None and self.target <= 0:
            raise ValidationError({"target": "Цена должна быть положительной."})


class Notification(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications"
    )
    item = models.ForeignKey(WatchItem, on_delete=models.SET_NULL, null=True)
    event_key = models.CharField(max_length=120, unique=True)
    message = models.CharField(max_length=500)
    price = money()
    observed_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at", "-pk")


class Portfolio(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="portfolios"
    )
    name = models.CharField("Название", max_length=100)
    currency = models.CharField("Валюта", max_length=20)
    initial_cash = money("Начальный капитал", validators=[MinValueValidator(0)])
    cash = money(default=0, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("name", "pk")
        constraints = [
            models.UniqueConstraint(
                fields=("owner", "name"), name="unique_owner_portfolio"
            ),
            models.CheckConstraint(
                condition=Q(cash__gte=0), name="nonnegative_portfolio_cash"
            ),
            models.CheckConstraint(
                condition=Q(initial_cash__gte=0), name="nonnegative_initial_cash"
            ),
        ]

    def __str__(self):
        return f"{self.name} ({self.currency})"


class Position(models.Model):
    portfolio = models.ForeignKey(
        Portfolio, on_delete=models.CASCADE, related_name="positions"
    )
    share = models.ForeignKey("dashboard.Share", on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField(default=0)
    cost_basis = money(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("portfolio", "share"), name="unique_portfolio_share"
            ),
            models.CheckConstraint(
                condition=Q(cost_basis__gte=0), name="nonnegative_position_cost"
            ),
            models.CheckConstraint(
                condition=Q(quantity__gt=0) | Q(cost_basis=0),
                name="closed_position_zero_cost",
            ),
        ]

    @property
    def average_price(self):
        return (
            (self.cost_basis / self.quantity).quantize(QUANTUM, rounding=ROUND_HALF_UP)
            if self.quantity
            else Decimal(0)
        )


class Strategy(models.Model):
    class Action(models.TextChoices):
        BUY = "buy", "Покупка"
        SELL = "sell", "Продажа"

    portfolio = models.ForeignKey(
        Portfolio, on_delete=models.CASCADE, related_name="strategies"
    )
    share = models.ForeignKey("dashboard.Share", on_delete=models.PROTECT)
    name = models.CharField("Название", max_length=100)
    quantity = models.PositiveIntegerField(
        "Количество следующей покупки", validators=[MinValueValidator(1)]
    )
    buy_below = money("Покупать не выше", validators=[MinValueValidator(QUANTUM)])
    sell_above = money("Продавать не ниже", validators=[MinValueValidator(QUANTUM)])
    active = models.BooleanField("Активна", default=True)
    next_action = models.CharField(
        max_length=4, choices=Action, default=Action.BUY, editable=False
    )
    cycle_quantity = models.PositiveIntegerField(default=0, editable=False)
    cycle_cost = money(default=0, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("pk",)
        constraints = [
            models.CheckConstraint(
                condition=Q(quantity__gt=0), name="positive_strategy_quantity"
            ),
            models.CheckConstraint(
                condition=Q(buy_below__gt=0) & Q(sell_above__gt=models.F("buy_below")),
                name="ordered_strategy_thresholds",
            ),
        ]

    def clean(self):
        if (
            self.buy_below is not None
            and self.sell_above is not None
            and self.buy_below >= self.sell_above
        ):
            raise ValidationError(
                {"sell_above": "Порог продажи должен быть выше порога покупки."}
            )
        if (
            self.portfolio_id
            and self.share_id
            and self.portfolio.currency.lower() != self.share.currency.lower()
        ):
            raise ValidationError(
                {"share": "Валюты акции и портфеля должны совпадать."}
            )


class Trade(models.Model):
    portfolio = models.ForeignKey(
        Portfolio, on_delete=models.CASCADE, related_name="trades"
    )
    share = models.ForeignKey("dashboard.Share", on_delete=models.PROTECT)
    side = models.CharField(max_length=4, choices=Strategy.Action)
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    price = money()
    amount = money()
    realized_pnl = money(default=0)
    request_id = models.UUIDField(default=uuid.uuid4)
    strategy = models.ForeignKey(
        Strategy, on_delete=models.SET_NULL, null=True, blank=True
    )
    automated = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at", "-pk")
        constraints = [
            models.UniqueConstraint(
                fields=("portfolio", "request_id"),
                name="unique_portfolio_trade_request",
            ),
            models.CheckConstraint(
                condition=Q(quantity__gt=0) & Q(price__gt=0) & Q(amount__gt=0),
                name="positive_trade_values",
            ),
        ]


class StrategyRun(models.Model):
    strategy = models.ForeignKey(
        Strategy, on_delete=models.SET_NULL, null=True, related_name="runs"
    )
    portfolio = models.ForeignKey(
        Portfolio, on_delete=models.CASCADE, related_name="strategy_runs"
    )
    strategy_name = models.CharField(max_length=100)
    quote = models.ForeignKey(PricePoint, on_delete=models.PROTECT)
    event_key = models.CharField(max_length=120, unique=True)
    trade = models.OneToOneField(Trade, on_delete=models.SET_NULL, null=True)
    action = models.CharField(max_length=4, choices=Strategy.Action)
    status = models.CharField(
        max_length=10, choices=[("executed", "Выполнено"), ("rejected", "Отклонено")]
    )
    reason = models.CharField(max_length=300, blank=True)
    profit = money(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at", "-pk")
