from django.urls import include, path, re_path

from dashboard.views import (
    NotificationListView,
    NotificationMarkReadView,
    PortfolioDashboardView,
    PortfolioTradeView,
    ShareCreateView,
    ShareDeleteView,
    ShareDetailView,
    ShareListView,
    SharePriceHistoryView,
    ShareUpdateView,
    StrategyDeleteView,
    StrategyDetailView,
    StrategyListView,
    StrategyRunView,
    StrategyToggleActiveView,
    WatchlistDeleteView,
    WatchlistListView,
)

app_name = "dashboard"

urlpatterns = [
    # Каталог акций
    path("", ShareListView.as_view(), name="index"),
    path("<int:pk>", ShareDetailView.as_view(), name="detail"),
    path("<int:pk>/", ShareDetailView.as_view()),
    path("create", ShareCreateView.as_view(), name="create"),
    path("create/", ShareCreateView.as_view()),
    path("update/<int:pk>", ShareUpdateView.as_view(), name="update"),
    path("update/<int:pk>/", ShareUpdateView.as_view()),
    path("delete/<int:pk>", ShareDeleteView.as_view(), name="delete"),
    path("delete/<int:pk>/", ShareDeleteView.as_view()),
    path("shares/<int:pk>/history/", SharePriceHistoryView.as_view(), name="price_history"),

    # Виртуальный инвестиционный портфель (Задание 4.2)
    path("portfolio/", PortfolioDashboardView.as_view(), name="portfolio"),
    path("portfolio/trade/", PortfolioTradeView.as_view(), name="portfolio_trade"),

    # Персональный мониторинг и уведомления (Задание 4.1)
    path("watchlist/", WatchlistListView.as_view(), name="watchlist"),
    path("watchlist/delete/<int:pk>/", WatchlistDeleteView.as_view(), name="watchlist_delete"),
    path("notifications/", NotificationListView.as_view(), name="notifications"),
    path("notifications/read/", NotificationMarkReadView.as_view(), name="notifications_read_all"),
    path("notifications/read/<int:pk>/", NotificationMarkReadView.as_view(), name="notification_read"),

    # Симулятор инвестиционных стратегий (Задание 4.4)
    path("strategies/", StrategyListView.as_view(), name="strategies"),
    path("strategies/<int:pk>/", StrategyDetailView.as_view(), name="strategy_detail"),
    path("strategies/<int:pk>/run/", StrategyRunView.as_view(), name="strategy_run"),
    path("strategies/<int:pk>/toggle/", StrategyToggleActiveView.as_view(), name="strategy_toggle"),
    path("strategies/<int:pk>/delete/", StrategyDeleteView.as_view(), name="strategy_delete"),

    # API
    path("api/", include("dashboard.api.urls")),
]
