from django.contrib.auth import login, logout
from django.db import IntegrityError, transaction
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views.generic import FormView, View

from .forms import AuthForm, RegistrationForm


class AuthView(FormView):
    template_name = "user/auth.html"
    form_class = AuthForm
    success_url = reverse_lazy("dashboard:index")

    def get_form_kwargs(self):
        return {**super().get_form_kwargs(), "request": self.request}

    def form_valid(self, form):
        login(self.request, form.user)
        return super().form_valid(form)


class RegistrationView(FormView):
    template_name = "user/registration.html"
    form_class = RegistrationForm
    success_url = reverse_lazy("dashboard:index")

    def form_valid(self, form):
        try:
            with transaction.atomic():
                user = form.save()
        except IntegrityError:
            form.add_error("email", "Данный e-mail уже зарегистрирован!")
            return self.form_invalid(form)
        login(self.request, user, backend="user.backends.CaseInsensitiveModelBackend")
        return super().form_valid(form)


class LogoutView(View):
    def get(self, request):
        return render(request, "user/logout.html")

    def post(self, request):
        logout(request)
        return redirect("dashboard:index")
