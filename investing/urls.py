from django.urls import path

from . import views

app_name = "investing"
urlpatterns = [
    path("workspace/", views.workspace, name="workspace"),
    path("watchlists/new/", views.watchlist_create, name="watchlist-create"),
    path("watchlists/<int:pk>/", views.watchlist_detail, name="watchlist"),
    path(
        "watchlists/<int:pk>/delete/", views.watchlist_delete, name="watchlist-delete"
    ),
    path("watch-items/<int:pk>/edit/", views.watch_item_edit, name="watch-item-edit"),
    path(
        "watch-items/<int:pk>/delete/",
        views.watch_item_delete,
        name="watch-item-delete",
    ),
    path("notifications/", views.notifications, name="notifications"),
    path(
        "notifications/<int:pk>/read/",
        views.notification_read,
        name="notification-read",
    ),
    path("portfolios/new/", views.portfolio_create, name="portfolio-create"),
    path("portfolios/<int:pk>/", views.portfolio_detail, name="portfolio"),
    path("portfolios/<int:pk>/trade/", views.trade_create, name="trade"),
    path("strategies/new/", views.strategy_edit, name="strategy-create"),
    path("strategies/<int:pk>/edit/", views.strategy_edit, name="strategy-edit"),
    path("strategies/<int:pk>/delete/", views.strategy_delete, name="strategy-delete"),
    path("shares/<int:pk>/history/", views.price_history, name="history"),
]
