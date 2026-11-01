from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

urlpatterns = [
    path("admin/", admin.site.urls),
    # Canonical user routes: /user/login/, /user/registration/, /user/logout/.
    path("user/", include("user.urls")),
    # Backwards-compatible redirects for the old concatenated URLs.
    path(
        "userlogin/",
        RedirectView.as_view(pattern_name="user:auth", permanent=False),
        name="legacy-login",
    ),
    path(
        "userregistration/",
        RedirectView.as_view(pattern_name="user:registration", permanent=False),
        name="legacy-registration",
    ),
    path(
        "userlogout/",
        RedirectView.as_view(pattern_name="user:logout", permanent=False),
        name="legacy-logout",
    ),
    path("", include("dashboard.urls")),
]
