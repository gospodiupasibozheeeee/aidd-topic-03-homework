from rest_framework import routers

from .views import (
    PortfolioTransactionViewSet,
    PortfolioViewSet,
    PriceHistoryViewSet,
    PriceNotificationViewSet,
    ShareViewSet,
    StrategyExecutionLogViewSet,
    TradingStrategyViewSet,
    WatchlistItemViewSet,
)

router = routers.DefaultRouter()
router.register(r"shares", ShareViewSet, basename="shares")
router.register(r"price-history", PriceHistoryViewSet, basename="price-history")
router.register(r"watchlist", WatchlistItemViewSet, basename="watchlist")
router.register(r"notifications", PriceNotificationViewSet, basename="notifications")
router.register(r"portfolio", PortfolioViewSet, basename="portfolio")
router.register(r"transactions", PortfolioTransactionViewSet, basename="transactions")
router.register(r"strategies", TradingStrategyViewSet, basename="strategies")
router.register(r"strategy-logs", StrategyExecutionLogViewSet, basename="strategy-logs")
