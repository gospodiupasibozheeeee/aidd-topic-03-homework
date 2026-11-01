from django.contrib import admin
from django.urls import include, path

from user.views import AuthView, LogoutView, RegistrationView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("dashboard.urls")),
    path("user/", include("user.urls")),
    # Обратная совместимость с устаревшими маршрутами без слэша
    path("userlogin/", AuthView.as_view()),
    path("userregistration/", RegistrationView.as_view()),
    path("userlogout/", LogoutView.as_view()),
]
