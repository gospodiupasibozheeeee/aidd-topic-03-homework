from django.contrib import admin
from django.urls import include, path

from user.views import AuthView, LogoutView, RegistrationView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("dashboard.urls")),
    path("user/", include("user.urls")),
    # Preserve existing bookmarks; named links use the corrected prefix.
    path("userlogin/", AuthView.as_view()),
    path("userregistration/", RegistrationView.as_view()),
    path("userlogout/", LogoutView.as_view()),
]
