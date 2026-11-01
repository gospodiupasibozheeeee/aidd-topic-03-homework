from django.urls import include, path
from django.views.generic import RedirectView

from dashboard.views import (
    ShareCreateView,
    ShareDeleteView,
    ShareDetailView,
    ShareListView,
    ShareUpdateView,
)

app_name = "dashboard"

urlpatterns = [
    path("", ShareListView.as_view(), name="index"),
    path("<int:pk>", ShareDetailView.as_view(), name="detail"),
    path("create", ShareCreateView.as_view(), name="create"),
    path("update/<int:pk>", ShareUpdateView.as_view(), name="update"),
    path("delete/<int:pk>", ShareDeleteView.as_view(), name="delete"),
    # Accept canonical trailing-slash variants and redirect to the original
    # paths used by templates and existing links.
    path(
        "create/",
        RedirectView.as_view(pattern_name="dashboard:create", permanent=False),
    ),
    path(
        "update/<int:pk>/",
        RedirectView.as_view(pattern_name="dashboard:update", permanent=False),
    ),
    path(
        "delete/<int:pk>/",
        RedirectView.as_view(pattern_name="dashboard:delete", permanent=False),
    ),
    path("api/", include("dashboard.api.urls")),
]
