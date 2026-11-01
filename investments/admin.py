from django.contrib import admin

from investments.models import (
    Notification,
    Portfolio,
    PriceSnapshot,
    Strategy,
    StrategyTrade,
    Transaction,
    Watchlist,
    WatchlistItem,
)


class TransactionInline(admin.TabularInline):
    model = Transaction
    extra = 0
    readonly_fields = ("executed_at",)


@admin.register(Portfolio)
class PortfolioAdmin(admin.ModelAdmin):
    list_display = ("name", "user", "created_at")
    search_fields = ("name", "user__email")
    inlines = (TransactionInline,)


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ("portfolio", "share", "side", "quantity", "price", "executed_at")
    list_filter = ("side", "share")
    search_fields = ("portfolio__name", "share__ticker", "share__name")


class WatchlistItemInline(admin.TabularInline):
    model = WatchlistItem
    extra = 0


@admin.register(Watchlist)
class WatchlistAdmin(admin.ModelAdmin):
    list_display = ("name", "user", "created_at")
    search_fields = ("name", "user__email")
    inlines = (WatchlistItemInline,)


@admin.register(WatchlistItem)
class WatchlistItemAdmin(admin.ModelAdmin):
    list_display = ("watchlist", "share", "target_price", "direction", "is_active")
    list_filter = ("direction", "is_active")
    search_fields = ("watchlist__name", "share__ticker", "share__name")


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("title", "user", "kind", "is_read", "created_at")
    list_filter = ("kind", "is_read")
    search_fields = ("title", "message", "user__email")


@admin.register(PriceSnapshot)
class PriceSnapshotAdmin(admin.ModelAdmin):
    list_display = ("share", "price", "captured_at", "source")
    list_filter = ("source", "share")
    search_fields = ("share__ticker", "share__name")


class StrategyTradeInline(admin.TabularInline):
    model = StrategyTrade
    extra = 0
    readonly_fields = ("executed_at", "cash_after", "position_after", "pnl")


@admin.register(Strategy)
class StrategyAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "user",
        "share",
        "is_active",
        "cash",
        "position_quantity",
        "realized_pnl",
    )
    list_filter = ("is_active", "share")
    search_fields = ("name", "user__email", "share__ticker")
    inlines = (StrategyTradeInline,)


@admin.register(StrategyTrade)
class StrategyTradeAdmin(admin.ModelAdmin):
    list_display = ("strategy", "side", "price", "quantity", "executed_at", "pnl")
    list_filter = ("side", "strategy")
    search_fields = ("strategy__name", "strategy__share__ticker")
