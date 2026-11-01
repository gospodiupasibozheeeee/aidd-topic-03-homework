from __future__ import annotations

from django.contrib import messages
from django.contrib.auth import login, logout
from django.db import IntegrityError
from django.shortcuts import redirect, render
from django.views.generic import View

from .forms import AuthForm, RegistrationForm


class AuthView(View):
    """Log in an existing user."""

    @staticmethod
    def get(request):
        return render(request, "user/auth.html", {"form": AuthForm()})

    @staticmethod
    def post(request):
        form = AuthForm(request.POST)

        if form.is_valid():
            login(request, form.user)
            return redirect("dashboard:index")

        return render(request, "user/auth.html", {"form": form})


class RegistrationView(View):
    """Register a new user and log them in."""

    @staticmethod
    def get(request):
        return render(request, "user/registration.html", {"form": RegistrationForm()})

    @staticmethod
    def post(request):
        form = RegistrationForm(request.POST)

        if form.is_valid():
            try:
                user = form.save()
            except IntegrityError:
                # The unique e-mail check is not atomic; handle a concurrent
                # registration gracefully instead of returning HTTP 500.
                form.add_error(
                    "email",
                    "Данный e-mail уже зарегистрирован. Попробуйте войти.",
                )
            else:
                login(request, user)
                messages.success(request, "Регистрация завершена.")
                return redirect("dashboard:index")

        return render(request, "user/registration.html", {"form": form})


class LogoutView(View):
    """Log out via POST; GET is kept as a safe redirect for old links."""

    @staticmethod
    def get(request):
        return redirect("dashboard:index")

    @staticmethod
    def post(request):
        logout(request)
        messages.success(request, "Вы вышли из системы.")
        return redirect("dashboard:index")
