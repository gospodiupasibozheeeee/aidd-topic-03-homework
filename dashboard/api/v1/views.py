from django_filters import rest_framework as filters
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response

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
from dashboard.services.history_service import calculate_price_dynamics
from dashboard.services.portfolio_service import buy_share, get_or_create_portfolio, sell_share
from dashboard.services.strategy_service import execute_strategy

from .serializer import (
    PortfolioPositionSerializer,
    PortfolioSerializer,
    PortfolioTransactionSerializer,
    PriceHistorySerializer,
    PriceNotificationSerializer,
    ShareSerializer,
    StrategyExecutionLogSerializer,
    TradingStrategySerializer,
    WatchlistItemSerializer,
)


class ShareFilter(filters.FilterSet):
    class Meta:
        model = Share
        fields = ("name", "ticker")


class ShareViewSet(viewsets.ModelViewSet):
    serializer_class = ShareSerializer
    queryset = Share.objects.all()
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    filter_backends = (OrderingFilter, filters.DjangoFilterBackend, SearchFilter)
    filterset_class = ShareFilter
    ordering_fields = ["name", "ticker"]
    search_fields = ["$name"]

    @action(detail=True, methods=["get"], url_path="dynamics")
    def dynamics(self, request, pk=None):
        share = self.get_object()
        period = request.query_params.get("period", "1M")
        data = calculate_price_dynamics(share, period=period)
        return Response(data)


class PriceHistoryViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = PriceHistorySerializer
    queryset = PriceHistory.objects.all().select_related("share")
    permission_classes = [permissions.AllowAny]
    filter_backends = (filters.DjangoFilterBackend, OrderingFilter)
    filterset_fields = ("share", "share__ticker")
    ordering_fields = ("recorded_at", "price")
    ordering = ("-recorded_at",)


class WatchlistItemViewSet(viewsets.ModelViewSet):
    serializer_class = WatchlistItemSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return WatchlistItem.objects.filter(user=self.request.user).select_related("share")

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class PriceNotificationViewSet(viewsets.ModelViewSet):
    serializer_class = PriceNotificationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return PriceNotification.objects.filter(user=self.request.user).select_related("share")

    @action(detail=False, methods=["post"], url_path="mark-all-read")
    def mark_all_read(self, request):
        PriceNotification.objects.filter(user=request.user, is_read=False).update(is_read=True)
        return Response({"status": "ok"})


class PortfolioViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = PortfolioSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Portfolio.objects.filter(user=self.request.user).prefetch_related(
            "positions__share", "transactions__share"
        )

    @action(detail=False, methods=["get"], url_path="my")
    def my_portfolio(self, request):
        portfolio = get_or_create_portfolio(request.user)
        serializer = self.get_serializer(portfolio)
        return Response(serializer.data)

    @action(detail=False, methods=["post"], url_path="buy")
    def buy(self, request):
        portfolio = get_or_create_portfolio(request.user)
        share_id = request.data.get("share_id")
        quantity = int(request.data.get("quantity", 1))
        share = Share.objects.filter(id=share_id).first()
        if not share:
            return Response({"error": "Инструмент не найден"}, status=status.HTTP_400_BAD_REQUEST)

        tx, err = buy_share(portfolio, share, quantity)
        if tx:
            return Response(PortfolioTransactionSerializer(tx).data, status=status.HTTP_201_CREATED)
        return Response({"error": err}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=["post"], url_path="sell")
    def sell(self, request):
        portfolio = get_or_create_portfolio(request.user)
        share_id = request.data.get("share_id")
        quantity = int(request.data.get("quantity", 1))
        share = Share.objects.filter(id=share_id).first()
        if not share:
            return Response({"error": "Инструмент не найден"}, status=status.HTTP_400_BAD_REQUEST)

        tx, err = sell_share(portfolio, share, quantity)
        if tx:
            return Response(PortfolioTransactionSerializer(tx).data, status=status.HTTP_201_CREATED)
        return Response({"error": err}, status=status.HTTP_400_BAD_REQUEST)


class PortfolioTransactionViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = PortfolioTransactionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return PortfolioTransaction.objects.filter(
            portfolio__user=self.request.user
        ).select_related("share")


class TradingStrategyViewSet(viewsets.ModelViewSet):
    serializer_class = TradingStrategySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return TradingStrategy.objects.filter(user=self.request.user).select_related("share")

    def perform_create(self, serializer):
        portfolio = get_or_create_portfolio(self.request.user)
        serializer.save(user=self.request.user, portfolio=portfolio)

    @action(detail=True, methods=["post"], url_path="run")
    def run_strategy(self, request, pk=None):
        strategy = self.get_object()
        success, msg = execute_strategy(strategy)
        return Response({"success": success, "message": msg})


class StrategyExecutionLogViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = StrategyExecutionLogSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return StrategyExecutionLog.objects.filter(
            strategy__user=self.request.user
        ).select_related("strategy")
