from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import F, Q
from django.utils import timezone


class Portfolio(models.Model):
    """A virtual portfolio owned by one user."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="portfolios",
    )
    name = models.CharField(max_length=100, verbose_name="Название")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=("user", "name"), name="unique_portfolio_name_per_user"
            )
        ]

    def __str__(self) -> str:
        return self.name


class Transaction(models.Model):
    """A virtual buy/sell operation inside a portfolio."""

    class Side(models.TextChoices):
        BUY = "buy", "Покупка"
        SELL = "sell", "Продажа"

    portfolio = models.ForeignKey(
        Portfolio, on_delete=models.CASCADE, related_name="transactions"
    )
    share = models.ForeignKey(
        "dashboard.Share", on_delete=models.CASCADE, related_name="transactions"
    )
    side = models.CharField(max_length=4, choices=Side.choices)
    quantity = models.DecimalField(max_digits=20, decimal_places=8)
    price = models.DecimalField(max_digits=20, decimal_places=9)
    executed_at = models.DateTimeField(default=timezone.now)
    note = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-executed_at", "-id"]
        constraints = [
            models.CheckConstraint(
                condition=Q(quantity__gt=0), name="transaction_quantity_positive"
            ),
            models.CheckConstraint(
                condition=Q(price__gt=0), name="transaction_price_positive"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.get_side_display()} {self.quantity} {self.share.ticker}"


class Watchlist(models.Model):
    """A named list of shares monitored by one user."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="watchlists",
    )
    name = models.CharField(max_length=100, verbose_name="Название")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=("user", "name"), name="unique_watchlist_name_per_user"
            )
        ]

    def __str__(self) -> str:
        return self.name


class WatchlistItem(models.Model):
    """A share inside a watchlist with an optional target-price alert."""

    class Direction(models.TextChoices):
        ABOVE = "above", "Цена выше или равна"
        BELOW = "below", "Цена ниже или равна"

    watchlist = models.ForeignKey(
        Watchlist, on_delete=models.CASCADE, related_name="items"
    )
    share = models.ForeignKey(
        "dashboard.Share", on_delete=models.CASCADE, related_name="watchlist_items"
    )
    target_price = models.DecimalField(
        max_digits=20, decimal_places=9, null=True, blank=True
    )
    direction = models.CharField(
        max_length=5, choices=Direction.choices, default=Direction.ABOVE
    )
    is_active = models.BooleanField(default=True)
    alert_active = models.BooleanField(default=False)
    alert_epoch = models.PositiveIntegerField(default=0)
    last_notified_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["share__name"]
        constraints = [
            models.UniqueConstraint(
                fields=("watchlist", "share"),
                name="unique_share_per_watchlist",
            ),
            models.CheckConstraint(
                condition=Q(target_price__isnull=True) | Q(target_price__gt=0),
                name="watchlist_target_price_positive",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.watchlist}: {self.share.ticker}"


class Notification(models.Model):
    """In-app notification. dedupe_key makes repeated events idempotent."""

    class Kind(models.TextChoices):
        WATCHLIST = "watchlist", "Наблюдение"
        STRATEGY = "strategy", "Стратегия"
        SYSTEM = "system", "Система"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    kind = models.CharField(max_length=20, choices=Kind.choices)
    title = models.CharField(max_length=255)
    message = models.TextField()
    dedupe_key = models.CharField(max_length=255, unique=True)
    share = models.ForeignKey(
        "dashboard.Share",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notifications",
    )
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self) -> str:
        return f"{self.title} ({self.user})"


class PriceSnapshot(models.Model):
    """A saved market price used for history and charts."""

    share = models.ForeignKey(
        "dashboard.Share", on_delete=models.CASCADE, related_name="price_snapshots"
    )
    price = models.DecimalField(max_digits=20, decimal_places=9)
    captured_at = models.DateTimeField(default=timezone.now)
    source = models.CharField(max_length=30, default="market")

    class Meta:
        ordering = ["captured_at"]
        constraints = [
            models.UniqueConstraint(
                fields=("share", "captured_at"),
                name="unique_price_snapshot_per_share_time",
            ),
            models.CheckConstraint(
                condition=Q(price__gt=0), name="price_snapshot_positive"
            ),
        ]
        indexes = [
            models.Index(
                fields=("share", "captured_at"), name="price_snapshot_share_time_idx"
            )
        ]

    def __str__(self) -> str:
        return f"{self.share.ticker} {self.price} @ {self.captured_at}"


class Strategy(models.Model):
    """A simple virtual buy-low / sell-high strategy."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="strategies",
    )
    name = models.CharField(max_length=100, verbose_name="Название")
    share = models.ForeignKey(
        "dashboard.Share",
        on_delete=models.CASCADE,
        related_name="strategies",
        verbose_name="Акция",
    )
    buy_below = models.DecimalField(
        max_digits=20, decimal_places=9, verbose_name="Цена покупки, не выше"
    )
    sell_above = models.DecimalField(
        max_digits=20, decimal_places=9, verbose_name="Цена продажи, не ниже"
    )
    quantity = models.DecimalField(
        max_digits=20, decimal_places=8, verbose_name="Количество"
    )
    initial_cash = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        default=Decimal("100000.00"),
        verbose_name="Начальный капитал",
    )
    cash = models.DecimalField(
        max_digits=20, decimal_places=2, default=Decimal("100000.00")
    )
    position_quantity = models.DecimalField(
        max_digits=20, decimal_places=8, default=Decimal("0")
    )
    avg_price = models.DecimalField(
        max_digits=20, decimal_places=9, null=True, blank=True
    )
    realized_pnl = models.DecimalField(
        max_digits=20, decimal_places=2, default=Decimal("0")
    )
    is_active = models.BooleanField(default=True, verbose_name="Активна")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=("user", "name"), name="unique_strategy_name_per_user"
            ),
            models.CheckConstraint(
                condition=Q(quantity__gt=0), name="strategy_quantity_positive"
            ),
            models.CheckConstraint(
                condition=Q(initial_cash__gt=0), name="strategy_cash_positive"
            ),
            models.CheckConstraint(
                condition=Q(buy_below__lt=F("sell_above")),
                name="strategy_buy_below_sell_above",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.share.ticker})"

    def clean(self):
        super().clean()
        if self.buy_below is not None and self.sell_above is not None:
            if self.buy_below >= self.sell_above:
                from django.core.exceptions import ValidationError

                raise ValidationError("Цена покупки должна быть ниже цены продажи.")


class StrategyTrade(models.Model):
    """A virtual operation produced by a strategy."""

    class Side(models.TextChoices):
        BUY = "buy", "Покупка"
        SELL = "sell", "Продажа"

    strategy = models.ForeignKey(
        Strategy, on_delete=models.CASCADE, related_name="trades"
    )
    side = models.CharField(max_length=4, choices=Side.choices)
    price = models.DecimalField(max_digits=20, decimal_places=9)
    quantity = models.DecimalField(max_digits=20, decimal_places=8)
    executed_at = models.DateTimeField(default=timezone.now)
    reason = models.CharField(max_length=255)
    cash_after = models.DecimalField(max_digits=20, decimal_places=2)
    position_after = models.DecimalField(max_digits=20, decimal_places=8)
    pnl = models.DecimalField(max_digits=20, decimal_places=2, default=Decimal("0"))

    class Meta:
        ordering = ["executed_at", "id"]
        constraints = [
            models.CheckConstraint(
                condition=Q(quantity__gt=0), name="strategy_trade_quantity_positive"
            ),
            models.CheckConstraint(
                condition=Q(price__gt=0), name="strategy_trade_price_positive"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.get_side_display()} {self.quantity} @ {self.price}"
