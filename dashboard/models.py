from decimal import Decimal
import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


def default_share_uid():
    return str(uuid.uuid4())


class Share(models.Model):
    """Акция"""

    figi = models.CharField(max_length=255, unique=True, verbose_name="FIGI")
    isin = models.CharField(max_length=255, verbose_name="ISIN")
    name = models.CharField(max_length=255, verbose_name="Наименование компании")
    ticker = models.CharField(max_length=10, unique=True, verbose_name="Тикер")
    currency = models.CharField(max_length=20, verbose_name="Валюта")
    uid = models.CharField(
        max_length=255, unique=True, default=default_share_uid, verbose_name="UID"
    )
    last_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        blank=True,
        null=True,
        verbose_name="Текущая цена",
    )
    is_trend_high = models.BooleanField(
        blank=True, null=True, verbose_name="Растет цена"
    )
    updated_at = models.DateTimeField(
        auto_now=True, blank=True, null=True, verbose_name="Время обновления"
    )

    class Meta:
        verbose_name = "Акция"
        verbose_name_plural = "Акции"
        ordering = ["name"]

    def __str__(self):
        return f"{self.ticker} ({self.name})"


# ==============================================================================
# 1. История изменения рыночных цен (Price History)
# ==============================================================================

class PriceHistory(models.Model):
    """История изменения рыночной цены акции"""

    share = models.ForeignKey(
        Share,
        on_delete=models.CASCADE,
        related_name="price_history",
        verbose_name="Акция",
    )
    price = models.DecimalField(
        max_digits=12, decimal_places=2, verbose_name="Цена"
    )
    recorded_at = models.DateTimeField(
        default=timezone.now, db_index=True, verbose_name="Время фиксации"
    )

    class Meta:
        verbose_name = "История цены"
        verbose_name_plural = "История цен"
        ordering = ["-recorded_at"]
        indexes = [
            models.Index(fields=["share", "-recorded_at"]),
        ]

    def __str__(self):
        return f"{self.share.ticker} @ {self.price} ({self.recorded_at:%Y-%m-%d %H:%M})"


# ==============================================================================
# 2. Персональный мониторинг акций и уведомления (Watchlist & Alerts)
# ==============================================================================

class WatchlistItem(models.Model):
    """Элемент персонального списка наблюдения за акцией"""

    CONDITION_CHOICES = (
        ("ABOVE", "Цена выше или равна (>=)"),
        ("BELOW", "Цена ниже или равна (<=)"),
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="watchlist_items",
        verbose_name="Пользователь",
    )
    share = models.ForeignKey(
        Share,
        on_delete=models.CASCADE,
        related_name="watched_by",
        verbose_name="Акция",
    )
    target_price = models.DecimalField(
        max_digits=12, decimal_places=2, verbose_name="Целевая цена"
    )
    condition = models.CharField(
        max_length=10,
        choices=CONDITION_CHOICES,
        default="ABOVE",
        verbose_name="Условие",
    )
    is_active = models.BooleanField(default=True, verbose_name="Активно")
    is_triggered = models.BooleanField(
        default=False,
        verbose_name="Сработало",
        help_text="Флаг для предотвращения повторной отправки уведомлений на одном уровне",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Создано")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Обновлено")

    class Meta:
        verbose_name = "Отслеживаемая акция"
        verbose_name_plural = "Список наблюдения"
        unique_together = ("user", "share", "condition")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.email} -> {self.share.ticker} {self.condition} {self.target_price}"


class PriceNotification(models.Model):
    """Уведомление о достижении целевой цены акции"""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="price_notifications",
        verbose_name="Пользователь",
    )
    share = models.ForeignKey(
        Share,
        on_delete=models.CASCADE,
        related_name="notifications",
        verbose_name="Акция",
    )
    target_price = models.DecimalField(
        max_digits=12, decimal_places=2, verbose_name="Целевой уровень"
    )
    actual_price = models.DecimalField(
        max_digits=12, decimal_places=2, verbose_name="Фактическая цена"
    )
    message = models.TextField(verbose_name="Текст уведомления")
    is_read = models.BooleanField(default=False, verbose_name="Прочитано")
    created_at = models.DateTimeField(
        auto_now_add=True, verbose_name="Время уведомления"
    )

    class Meta:
        verbose_name = "Уведомление о цене"
        verbose_name_plural = "Уведомления о ценах"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Уведомление для {self.user.email}: {self.message}"


# ==============================================================================
# 3. Виртуальный инвестиционный портфель (Portfolio)
# ==============================================================================

class Portfolio(models.Model):
    """Виртуальный инвестиционный портфель пользователя"""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="portfolios",
        verbose_name="Пользователь",
    )
    name = models.CharField(
        max_length=100, default="Основной портфель", verbose_name="Название портфеля"
    )
    balance = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("100000.00"),
        verbose_name="Свободный баланс",
    )
    initial_balance = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("100000.00"),
        verbose_name="Начальный баланс",
    )
    currency = models.CharField(
        max_length=10, default="USD", verbose_name="Валюта портфеля"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Создан")

    class Meta:
        verbose_name = "Инвестиционный портфель"
        verbose_name_plural = "Инвестиционные портфели"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} ({self.user.email})"

    @property
    def invested_value(self) -> Decimal:
        """Суммарная рыночная стоимость открытых позиций"""
        total = Decimal("0.00")
        for pos in self.positions.filter(quantity__gt=0):
            total += pos.current_value
        return total

    @property
    def total_value(self) -> Decimal:
        """Общая стоимость портфеля (баланс + рыночная стоимость активов)"""
        return self.balance + self.invested_value

    @property
    def total_pnl(self) -> Decimal:
        """Абсолютная прибыль / убыток портфеля относительно начального баланса"""
        return self.total_value - self.initial_balance

    @property
    def total_pnl_percent(self) -> Decimal:
        """Процентная доходность портфеля"""
        if self.initial_balance > Decimal("0.00"):
            return ((self.total_pnl) / self.initial_balance) * Decimal("100.00")
        return Decimal("0.00")


class PortfolioPosition(models.Model):
    """Позиция портфеля по конкретной акции"""

    portfolio = models.ForeignKey(
        Portfolio,
        on_delete=models.CASCADE,
        related_name="positions",
        verbose_name="Портфель",
    )
    share = models.ForeignKey(
        Share,
        on_delete=models.CASCADE,
        related_name="positions",
        verbose_name="Акция",
    )
    quantity = models.PositiveIntegerField(default=0, verbose_name="Количество")
    average_buy_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name="Средняя цена покупки",
    )
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Обновлено")

    class Meta:
        verbose_name = "Позиция портфеля"
        verbose_name_plural = "Позиции портфеля"
        unique_together = ("portfolio", "share")

    def __str__(self):
        return f"{self.portfolio.name}: {self.share.ticker} x {self.quantity}"

    @property
    def total_cost(self) -> Decimal:
        """Суммарная себестоимость приобретения текущего объема"""
        return Decimal(self.quantity) * self.average_buy_price

    @property
    def current_value(self) -> Decimal:
        """Текущая рыночная стоимость позиции"""
        price = self.share.last_price or self.average_buy_price
        return Decimal(self.quantity) * price

    @property
    def unrealized_pnl(self) -> Decimal:
        """Нереализованная прибыль / убыток по позиции"""
        return self.current_value - self.total_cost

    @property
    def unrealized_pnl_percent(self) -> Decimal:
        """Нереализованная доходность в процентах"""
        if self.total_cost > Decimal("0.00"):
            return (self.unrealized_pnl / self.total_cost) * Decimal("100.00")
        return Decimal("0.00")


class PortfolioTransaction(models.Model):
    """Журнал операций (сделок) с акциями в портфеле"""

    TYPE_CHOICES = (
        ("BUY", "Покупка"),
        ("SELL", "Продажа"),
    )

    portfolio = models.ForeignKey(
        Portfolio,
        on_delete=models.CASCADE,
        related_name="transactions",
        verbose_name="Портфель",
    )
    share = models.ForeignKey(
        Share,
        on_delete=models.CASCADE,
        related_name="transactions",
        verbose_name="Акция",
    )
    strategy = models.ForeignKey(
        "TradingStrategy",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="transactions",
        verbose_name="Стратегия",
    )
    transaction_type = models.CharField(
        max_length=4, choices=TYPE_CHOICES, verbose_name="Тип операции"
    )
    quantity = models.PositiveIntegerField(verbose_name="Количество акций")
    price = models.DecimalField(
        max_digits=12, decimal_places=2, verbose_name="Цена исполнения"
    )
    total_amount = models.DecimalField(
        max_digits=14, decimal_places=2, verbose_name="Сумма сделки"
    )
    realized_pnl = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name="Реализованная прибыль/убыток",
    )
    created_at = models.DateTimeField(
        auto_now_add=True, verbose_name="Время сделки"
    )

    class Meta:
        verbose_name = "Сделка"
        verbose_name_plural = "История сделок"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.transaction_type} {self.quantity} {self.share.ticker} @ {self.price}"


# ==============================================================================
# 4. Симулятор инвестиционных стратегий (Strategy Simulator)
# ==============================================================================

class TradingStrategy(models.Model):
    """Инвестиционная торговая стратегия"""

    STRATEGY_TYPE_CHOICES = (
        ("THRESHOLD_BUY_SELL", "Пороговая (покупка при цене <= P1, продажа при цене >= P2)"),
        ("DIP_BUY_PROFIT_SELL", "Процентная (покупка при падении на X%, фиксация прибыли при росте на Y%)"),
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="strategies",
        verbose_name="Пользователь",
    )
    portfolio = models.ForeignKey(
        Portfolio,
        on_delete=models.CASCADE,
        related_name="strategies",
        verbose_name="Портфель",
    )
    share = models.ForeignKey(
        Share,
        on_delete=models.CASCADE,
        related_name="strategies",
        verbose_name="Инструмент",
    )
    name = models.CharField(max_length=150, verbose_name="Название стратегии")
    strategy_type = models.CharField(
        max_length=30,
        choices=STRATEGY_TYPE_CHOICES,
        default="THRESHOLD_BUY_SELL",
        verbose_name="Тип стратегии",
    )
    buy_threshold = models.DecimalField(
        max_digits=12, decimal_places=2, verbose_name="Уровень покупки (цена или %)"
    )
    sell_threshold = models.DecimalField(
        max_digits=12, decimal_places=2, verbose_name="Уровень продажи (цена или %)"
    )
    trade_quantity = models.PositiveIntegerField(
        default=1, verbose_name="Количество акций в сделке"
    )
    is_active = models.BooleanField(default=True, verbose_name="Активна")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Создана")

    class Meta:
        verbose_name = "Торговая стратегия"
        verbose_name_plural = "Торговые стратегии"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} ({self.share.ticker})"

    @property
    def total_trades(self) -> int:
        return self.logs.filter(action__in=["BUY", "SELL"]).count()

    @property
    def total_pnl(self) -> Decimal:
        """Суммарный реализованный PnL от сделок данной стратегии"""
        pnl_sum = self.transactions.aggregate(models.Sum("realized_pnl"))["realized_pnl__sum"]
        return pnl_sum or Decimal("0.00")



class StrategyExecutionLog(models.Model):
    """Журнал операций симулятора инвестиционных стратегий"""

    ACTION_CHOICES = (
        ("BUY", "Покупка"),
        ("SELL", "Продажа"),
        ("SKIP", "Пропуск"),
    )

    strategy = models.ForeignKey(
        TradingStrategy,
        on_delete=models.CASCADE,
        related_name="logs",
        verbose_name="Стратегия",
    )
    action = models.CharField(
        max_length=10, choices=ACTION_CHOICES, verbose_name="Действие"
    )
    price = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True, verbose_name="Цена"
    )
    quantity = models.PositiveIntegerField(default=0, verbose_name="Количество")
    message = models.TextField(verbose_name="Описание события")
    executed_at = models.DateTimeField(
        auto_now_add=True, verbose_name="Время выполнения"
    )

    class Meta:
        verbose_name = "Лог выполнения стратегии"
        verbose_name_plural = "Журнал симулятора"
        ordering = ["-executed_at"]

    def __str__(self):
        return f"[{self.executed_at:%Y-%m-%d %H:%M}] {self.strategy.name}: {self.action}"
