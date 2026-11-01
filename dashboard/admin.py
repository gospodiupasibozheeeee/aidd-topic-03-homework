from django.contrib import admin

from dashboard.models import (
    Portfolio,
    PortfolioPosition,
    PortfolioTransaction,
    PriceHistory,
    PriceNotification,
    Share,
    StrategyExecutionLog,
    TradingStrategy,
    WatchlistItem,
)


@admin.register(Share)
class ShareAdmin(admin.ModelAdmin):
    list_display = ("ticker", "name", "figi", "isin", "currency", "last_price", "is_trend_high", "updated_at")
    list_filter = ("currency", "is_trend_high")
    search_fields = ("figi", "isin", "name", "ticker", "uid")
    readonly_fields = ("updated_at",)


@admin.register(PriceHistory)
class PriceHistoryAdmin(admin.ModelAdmin):
    list_display = ("share", "price", "recorded_at")
    list_filter = ("share",)
    search_fields = ("share__ticker", "share__name")
    readonly_fields = ("recorded_at",)


@admin.register(WatchlistItem)
class WatchlistItemAdmin(admin.ModelAdmin):
    list_display = ("user", "share", "condition", "target_price", "is_active", "is_triggered", "created_at")
    list_filter = ("condition", "is_active", "is_triggered")
    search_fields = ("user__email", "share__ticker")


@admin.register(PriceNotification)
class PriceNotificationAdmin(admin.ModelAdmin):
    list_display = ("user", "share", "target_price", "actual_price", "is_read", "created_at")
    list_filter = ("is_read", "created_at")
    search_fields = ("user__email", "share__ticker", "message")


class PortfolioPositionInline(admin.TabularInline):
    model = PortfolioPosition
    extra = 0


@admin.register(Portfolio)
class PortfolioAdmin(admin.ModelAdmin):
    list_display = ("name", "user", "balance", "initial_balance", "currency", "created_at")
    search_fields = ("name", "user__email")
    inlines = [PortfolioPositionInline]


@admin.register(PortfolioTransaction)
class PortfolioTransactionAdmin(admin.ModelAdmin):
    list_display = ("portfolio", "transaction_type", "share", "quantity", "price", "total_amount", "realized_pnl", "created_at")
    list_filter = ("transaction_type", "created_at")
    search_fields = ("portfolio__user__email", "share__ticker")


@admin.register(TradingStrategy)
class TradingStrategyAdmin(admin.ModelAdmin):
    list_display = ("name", "user", "share", "strategy_type", "buy_threshold", "sell_threshold", "trade_quantity", "is_active")
    list_filter = ("strategy_type", "is_active")
    search_fields = ("name", "user__email", "share__ticker")


@admin.register(StrategyExecutionLog)
class StrategyExecutionLogAdmin(admin.ModelAdmin):
    list_display = ("strategy", "action", "price", "quantity", "executed_at")
    list_filter = ("action", "executed_at")
    search_fields = ("strategy__name", "message")

