from decimal import Decimal

from django.core.exceptions import ValidationError as ModelValidationError
from django.db import IntegrityError
from django.utils import timezone
from rest_framework import mixins, permissions, serializers, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from dashboard.models import Share

from .forms import HistoryRangeForm
from .models import (
    Notification,
    Portfolio,
    PricePoint,
    Strategy,
    StrategyRun,
    Trade,
    WatchItem,
    Watchlist,
)
from .services.history import history_data
from .services.monitoring import save_watch_item
from .services.strategies import save_strategy, strategy_summary
from .services.trading import (
    TradeConflict,
    create_portfolio,
    execute_trade,
    portfolio_summary,
)


def decimal_payload(value):
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, dict):
        return {key: decimal_payload(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [decimal_payload(item) for item in value]
    return value


class PrivateViewSet(viewsets.GenericViewSet):
    permission_classes = [permissions.IsAuthenticated]

    def handle_exception(self, exc):
        if isinstance(exc, TradeConflict):
            return Response({"detail": exc.messages}, status=409)
        if isinstance(exc, ModelValidationError):
            exc = ValidationError(
                exc.message_dict if hasattr(exc, "message_dict") else exc.messages
            )
        elif isinstance(exc, IntegrityError):
            exc = ValidationError("Запись с такими данными уже существует.")
        return super().handle_exception(exc)


class WatchItemSerializer(serializers.ModelSerializer):
    ticker = serializers.CharField(source="share.ticker", read_only=True)

    class Meta:
        model = WatchItem
        fields = (
            "id",
            "watchlist",
            "share",
            "ticker",
            "target",
            "direction",
            "triggered_at",
        )
        read_only_fields = ("triggered_at",)
        extra_kwargs = {"target": {"coerce_to_string": True}}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["watchlist"].queryset = Watchlist.objects.filter(
            owner=self.context["request"].user
        )

    def create(self, validated_data):
        return save_watch_item(self.context["request"].user, **validated_data)

    def update(self, instance, validated_data):
        values = {
            field: getattr(instance, field)
            for field in ("watchlist", "share", "target", "direction")
        }
        return save_watch_item(
            self.context["request"].user,
            item_id=instance.pk,
            **{**values, **validated_data},
        )


class WatchlistSerializer(serializers.ModelSerializer):
    class Meta:
        model = Watchlist
        fields = ("id", "name", "created_at")
        read_only_fields = ("created_at",)

    def create(self, validated_data):
        item = Watchlist(owner=self.context["request"].user, **validated_data)
        item.full_clean()
        item.save()
        return item

    def update(self, instance, validated_data):
        instance.name = validated_data.get("name", instance.name)
        instance.full_clean()
        instance.save(update_fields=["name"])
        return instance


class WatchlistViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    PrivateViewSet,
):
    serializer_class = WatchlistSerializer

    def get_queryset(self):
        return Watchlist.objects.filter(owner=self.request.user)


class WatchItemViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    PrivateViewSet,
):
    serializer_class = WatchItemSerializer

    def get_queryset(self):
        queryset = WatchItem.objects.filter(
            watchlist__owner=self.request.user
        ).select_related("share")
        watchlist = self.request.query_params.get("watchlist")
        if watchlist is not None:
            identifier = serializers.IntegerField(
                min_value=1, max_value=2**63 - 1
            ).run_validation(watchlist)
            queryset = queryset.filter(watchlist_id=identifier)
        return queryset


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ("id", "message", "price", "observed_at", "created_at", "read_at")
        read_only_fields = fields
        extra_kwargs = {"price": {"coerce_to_string": True}}


class NotificationViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, PrivateViewSet
):
    serializer_class = NotificationSerializer

    def get_queryset(self):
        return Notification.objects.filter(owner=self.request.user)

    @action(detail=True, methods=["post"])
    def read(self, request, pk=None):
        item = self.get_object()
        if item.read_at is None:
            item.read_at = timezone.now()
            item.save(update_fields=["read_at"])
        return Response(self.get_serializer(item).data)


class TradeSerializer(serializers.ModelSerializer):
    ticker = serializers.CharField(source="share.ticker", read_only=True)

    class Meta:
        model = Trade
        fields = (
            "id",
            "share",
            "ticker",
            "side",
            "quantity",
            "price",
            "amount",
            "realized_pnl",
            "request_id",
            "automated",
            "strategy",
            "created_at",
        )
        read_only_fields = fields
        extra_kwargs = {
            field: {"coerce_to_string": True}
            for field in ("price", "amount", "realized_pnl")
        }


class TradeRequestSerializer(serializers.Serializer):
    share = serializers.PrimaryKeyRelatedField(queryset=Share.objects.all())
    side = serializers.ChoiceField(choices=Strategy.Action)
    quantity = serializers.IntegerField(min_value=1, max_value=2147483647)
    price = serializers.DecimalField(
        max_digits=24,
        decimal_places=9,
        required=False,
        min_value=Decimal("0.000000001"),
    )
    request_id = serializers.UUIDField()


class PortfolioSerializer(serializers.ModelSerializer):
    summary = serializers.SerializerMethodField()

    class Meta:
        model = Portfolio
        fields = (
            "id",
            "name",
            "currency",
            "initial_cash",
            "cash",
            "summary",
            "created_at",
        )
        read_only_fields = ("cash", "created_at")
        extra_kwargs = {
            field: {"coerce_to_string": True} for field in ("initial_cash", "cash")
        }

    def get_summary(self, obj):
        result = portfolio_summary(obj)
        result["holdings"] = [
            {**row, "share": row["share"].pk, "ticker": row["share"].ticker}
            for row in result["holdings"]
        ]
        return decimal_payload(result)

    def create(self, validated_data):
        return create_portfolio(self.context["request"].user, **validated_data)

    def update(self, instance, validated_data):
        if any(
            key in validated_data and validated_data[key] != getattr(instance, key)
            for key in ("currency", "initial_cash")
        ):
            raise ValidationError("Валюта и начальный капитал неизменны.")
        instance.name = validated_data.get("name", instance.name)
        instance.full_clean()
        instance.save(update_fields=["name"])
        return instance


class PortfolioViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    PrivateViewSet,
):
    serializer_class = PortfolioSerializer

    def get_queryset(self):
        return Portfolio.objects.filter(owner=self.request.user)

    @action(detail=True, methods=["get"], url_path="strategy-runs")
    def strategy_runs(self, request, pk=None):
        page = self.paginate_queryset(self.get_object().strategy_runs.all())
        return self.get_paginated_response(StrategyRunSerializer(page, many=True).data)

    @action(detail=True, methods=["get", "post"])
    def trades(self, request, pk=None):
        portfolio = self.get_object()
        if request.method == "GET":
            page = self.paginate_queryset(portfolio.trades.select_related("share"))
            return self.get_paginated_response(TradeSerializer(page, many=True).data)
        form = TradeRequestSerializer(data=request.data)
        form.is_valid(raise_exception=True)
        values = dict(form.validated_data)
        share = values.pop("share")
        trade, created = execute_trade(request.user, portfolio.pk, share.pk, **values)
        return Response(TradeSerializer(trade).data, status=201 if created else 200)


class StrategyRunSerializer(serializers.ModelSerializer):
    class Meta:
        model = StrategyRun
        fields = (
            "id",
            "strategy",
            "strategy_name",
            "quote",
            "trade",
            "action",
            "status",
            "reason",
            "profit",
            "created_at",
        )
        read_only_fields = fields
        extra_kwargs = {"profit": {"coerce_to_string": True}}


class StrategySerializer(serializers.ModelSerializer):
    summary = serializers.SerializerMethodField()

    class Meta:
        model = Strategy
        fields = (
            "id",
            "name",
            "portfolio",
            "share",
            "quantity",
            "buy_below",
            "sell_above",
            "active",
            "next_action",
            "cycle_quantity",
            "summary",
        )
        read_only_fields = ("next_action", "cycle_quantity")
        extra_kwargs = {
            field: {"coerce_to_string": True} for field in ("buy_below", "sell_above")
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["portfolio"].queryset = Portfolio.objects.filter(
            owner=self.context["request"].user
        )

    def get_summary(self, obj):
        return decimal_payload(strategy_summary(obj))

    def create(self, validated_data):
        return save_strategy(self.context["request"].user, **validated_data)

    def update(self, instance, validated_data):
        values = {
            field: getattr(instance, field)
            for field in (
                "portfolio",
                "share",
                "name",
                "quantity",
                "buy_below",
                "sell_above",
                "active",
            )
        }
        return save_strategy(
            self.context["request"].user,
            strategy_id=instance.pk,
            **{**values, **validated_data},
        )


class StrategyViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    PrivateViewSet,
):
    serializer_class = StrategySerializer

    def get_queryset(self):
        return Strategy.objects.filter(
            portfolio__owner=self.request.user
        ).select_related("portfolio")

    @action(detail=True, methods=["get"])
    def runs(self, request, pk=None):
        page = self.paginate_queryset(self.get_object().runs.all())
        return self.get_paginated_response(StrategyRunSerializer(page, many=True).data)


class PricePointSerializer(serializers.ModelSerializer):
    class Meta:
        model = PricePoint
        fields = ("id", "observed_at", "price", "currency")
        read_only_fields = fields
        extra_kwargs = {"price": {"coerce_to_string": True}}


def price_history_response(view, request, share):
    form = HistoryRangeForm(request.query_params)
    if not form.is_valid():
        raise ValidationError(form.errors)
    records, summary, daily = history_data(share, **form.cleaned_data)
    page = view.paginate_queryset(records)
    response = view.get_paginated_response(PricePointSerializer(page, many=True).data)
    response.data.update(summary=decimal_payload(summary), daily=decimal_payload(daily))
    return response
