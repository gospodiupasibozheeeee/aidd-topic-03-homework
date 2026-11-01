from django.contrib.auth import login, logout
from django.shortcuts import redirect, render
from django.views.generic import View

from .forms import AuthForm, RegistrationForm


class AuthView(View):
    """Авторизация пользователей"""

    @staticmethod
    def get(request):
        if request.user.is_authenticated:
            return redirect("dashboard:index")
        return render(request, "user/auth.html", {"form": AuthForm()})

    @staticmethod
    def post(request):
        form = AuthForm(request.POST, request=request)
        if form.is_valid():
            login(request, form.user)
            return redirect("dashboard:index")

        error_message = ""
        if form.non_field_errors():
            error_message = form.non_field_errors()[0]
        elif form.errors:
            # Первое сообщение об ошибке поля
            first_field = next(iter(form.errors))
            error_message = form.errors[first_field][0]

        return render(
            request,
            "user/auth.html",
            {
                "form": form,
                "error": error_message,
            },
        )


class RegistrationView(View):
    """Регистрация новых пользователей"""

    @staticmethod
    def get(request):
        if request.user.is_authenticated:
            return redirect("dashboard:index")
        return render(request, "user/registration.html", {"form": RegistrationForm()})

    @staticmethod
    def post(request):
        form = RegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user, backend="user.backends.CaseInsensitiveEmailBackend")
            return redirect("dashboard:index")

        error_message = ""
        if form.non_field_errors():
            error_message = form.non_field_errors()[0]
        elif form.errors:
            first_field = next(iter(form.errors))
            error_message = form.errors[first_field][0]

        return render(
            request,
            "user/registration.html",
            {
                "form": form,
                "error": error_message,
            },
        )


class LogoutView(View):
    """Выход из системы"""

    @staticmethod
    def get(request):
        logout(request)
        return redirect("dashboard:index")

    @staticmethod
    def post(request):
        logout(request)
        return redirect("dashboard:index")
