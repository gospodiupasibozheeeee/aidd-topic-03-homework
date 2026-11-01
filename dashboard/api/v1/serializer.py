from rest_framework import serializers

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


class ShareSerializer(serializers.ModelSerializer):
    uid = serializers.CharField(required=False, max_length=255)

    class Meta:
        model = Share
        fields = (
            "id",
            "figi",
            "isin",
            "name",
            "ticker",
            "currency",
            "uid",
            "last_price",
            "is_trend_high",
            "updated_at",
        )
        read_only_fields = ("id", "updated_at")


class PriceHistorySerializer(serializers.ModelSerializer):
    ticker = serializers.CharField(source="share.ticker", read_only=True)

    class Meta:
        model = PriceHistory
        fields = ("id", "share", "ticker", "price", "recorded_at")
        read_only_fields = ("id", "recorded_at")


class WatchlistItemSerializer(serializers.ModelSerializer):
    ticker = serializers.CharField(source="share.ticker", read_only=True)
    share_name = serializers.CharField(source="share.name", read_only=True)

    class Meta:
        model = WatchlistItem
        fields = (
            "id",
            "user",
            "share",
            "ticker",
            "share_name",
            "target_price",
            "condition",
            "is_active",
            "is_triggered",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "user", "is_triggered", "created_at", "updated_at")


class PriceNotificationSerializer(serializers.ModelSerializer):
    ticker = serializers.CharField(source="share.ticker", read_only=True)

    class Meta:
        model = PriceNotification
        fields = (
            "id",
            "user",
            "share",
            "ticker",
            "target_price",
            "actual_price",
            "message",
            "is_read",
            "created_at",
        )
        read_only_fields = ("id", "user", "created_at")


class PortfolioPositionSerializer(serializers.ModelSerializer):
    ticker = serializers.CharField(source="share.ticker", read_only=True)
    share_name = serializers.CharField(source="share.name", read_only=True)
    current_price = serializers.DecimalField(
        source="share.last_price", max_digits=12, decimal_places=2, read_only=True
    )
    current_value = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True
    )
    unrealized_pnl = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True
    )
    unrealized_pnl_percent = serializers.DecimalField(
        max_digits=8, decimal_places=2, read_only=True
    )

    class Meta:
        model = PortfolioPosition
        fields = (
            "id",
            "share",
            "ticker",
            "share_name",
            "quantity",
            "average_buy_price",
            "current_price",
            "current_value",
            "unrealized_pnl",
            "unrealized_pnl_percent",
            "updated_at",
        )


class PortfolioTransactionSerializer(serializers.ModelSerializer):
    ticker = serializers.CharField(source="share.ticker", read_only=True)

    class Meta:
        model = PortfolioTransaction
        fields = (
            "id",
            "portfolio",
            "share",
            "ticker",
            "strategy",
            "transaction_type",
            "quantity",
            "price",
            "total_amount",
            "realized_pnl",
            "created_at",
        )
        read_only_fields = ("id", "created_at")


class PortfolioSerializer(serializers.ModelSerializer):
    positions = PortfolioPositionSerializer(many=True, read_only=True)
    invested_value = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True
    )
    total_value = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True
    )
    total_pnl = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True
    )
    total_pnl_percent = serializers.DecimalField(
        max_digits=8, decimal_places=2, read_only=True
    )

    class Meta:
        model = Portfolio
        fields = (
            "id",
            "user",
            "name",
            "balance",
            "initial_balance",
            "currency",
            "invested_value",
            "total_value",
            "total_pnl",
            "total_pnl_percent",
            "positions",
            "created_at",
        )
        read_only_fields = ("id", "user", "created_at")


class TradingStrategySerializer(serializers.ModelSerializer):
    ticker = serializers.CharField(source="share.ticker", read_only=True)
    total_trades = serializers.IntegerField(read_only=True)
    total_pnl = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True
    )

    class Meta:
        model = TradingStrategy
        fields = (
            "id",
            "user",
            "portfolio",
            "share",
            "ticker",
            "name",
            "strategy_type",
            "buy_threshold",
            "sell_threshold",
            "trade_quantity",
            "is_active",
            "total_trades",
            "total_pnl",
            "created_at",
        )
        read_only_fields = ("id", "user", "portfolio", "created_at")


class StrategyExecutionLogSerializer(serializers.ModelSerializer):
    strategy_name = serializers.CharField(source="strategy.name", read_only=True)

    class Meta:
        model = StrategyExecutionLog
        fields = (
            "id",
            "strategy",
            "strategy_name",
            "action",
            "price",
            "quantity",
            "message",
            "executed_at",
        )
        read_only_fields = ("id", "executed_at")
