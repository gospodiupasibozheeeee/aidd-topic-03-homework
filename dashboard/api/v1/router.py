from rest_framework import routers

from .views import ShareViewSet

router = routers.DefaultRouter()
router.register(r"shares", ShareViewSet)

from investing.api import (
    NotificationViewSet,
    PortfolioViewSet,
    StrategyViewSet,
    WatchItemViewSet,
    WatchlistViewSet,
)

router.register("watchlists", WatchlistViewSet, basename="watchlist")
router.register("watch-items", WatchItemViewSet, basename="watch-item")
router.register("notifications", NotificationViewSet, basename="notification")
router.register("portfolios", PortfolioViewSet, basename="portfolio")
router.register("strategies", StrategyViewSet, basename="strategy")
