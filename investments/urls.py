from django.urls import path

from investments import views

app_name = "investments"

urlpatterns = [
    path("portfolios/", views.PortfolioListView.as_view(), name="portfolio-list"),
    path(
        "portfolios/create/",
        views.PortfolioCreateView.as_view(),
        name="portfolio-create",
    ),
    path(
        "portfolios/<int:pk>/",
        views.PortfolioDetailView.as_view(),
        name="portfolio-detail",
    ),
    path(
        "portfolios/<int:pk>/delete/",
        views.PortfolioDeleteView.as_view(),
        name="portfolio-delete",
    ),
    path("watchlists/", views.WatchlistListView.as_view(), name="watchlist-list"),
    path(
        "watchlists/create/",
        views.WatchlistCreateView.as_view(),
        name="watchlist-create",
    ),
    path(
        "watchlists/<int:pk>/",
        views.WatchlistDetailView.as_view(),
        name="watchlist-detail",
    ),
    path(
        "watchlists/<int:pk>/items/<int:item_pk>/delete/",
        views.WatchlistItemDeleteView.as_view(),
        name="watchlist-item-delete",
    ),
    path("notifications/", views.NotificationListView.as_view(), name="notifications"),
    path(
        "notifications/<int:pk>/read/",
        views.NotificationReadView.as_view(),
        name="notification-read",
    ),
    path("strategies/", views.StrategyListView.as_view(), name="strategy-list"),
    path(
        "strategies/create/",
        views.StrategyCreateView.as_view(),
        name="strategy-create",
    ),
    path(
        "strategies/<int:pk>/",
        views.StrategyDetailView.as_view(),
        name="strategy-detail",
    ),
    path(
        "strategies/<int:pk>/edit/",
        views.StrategyUpdateView.as_view(),
        name="strategy-update",
    ),
    path(
        "strategies/<int:pk>/delete/",
        views.StrategyDeleteView.as_view(),
        name="strategy-delete",
    ),
    path(
        "strategies/<int:pk>/evaluate/",
        views.StrategyEvaluateView.as_view(),
        name="strategy-evaluate",
    ),
    path(
        "strategies/<int:pk>/reset/",
        views.StrategyResetView.as_view(),
        name="strategy-reset",
    ),
    path("shares/<int:pk>/history/", views.price_history, name="price-history"),
]
