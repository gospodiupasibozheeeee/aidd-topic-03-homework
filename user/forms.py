from __future__ import annotations

from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from user.models import User


class RegistrationForm(forms.Form):
    """Registration by e-mail and password."""

    email = forms.EmailField(
        required=True,
        max_length=150,
        widget=forms.EmailInput(
            attrs={
                "class": "form-control mb-3",
                "placeholder": "Email",
                "autocomplete": "email",
            }
        ),
    )
    password1 = forms.CharField(
        required=True,
        label="Пароль",
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control mb-3",
                "placeholder": "Пароль",
                "autocomplete": "new-password",
            }
        ),
    )
    password2 = forms.CharField(
        required=True,
        label="Повторите пароль",
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control mb-3",
                "placeholder": "Повторите пароль",
                "autocomplete": "new-password",
            }
        ),
    )

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError(
                "Данный e-mail уже зарегистрирован! Введите другой e-mail или "
                "воспользуйтесь формой авторизации."
            )
        return email

    def clean_password1(self):
        password = self.cleaned_data.get("password1")
        if password:
            validate_password(password)
        return password

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get("password1")
        password2 = cleaned_data.get("password2")

        if password1 and password2 and password1 != password2:
            self.add_error("password2", "Введенные пароли не совпадают")

        return cleaned_data

    def save(self):
        email = self.cleaned_data["email"]
        password = self.cleaned_data["password1"]
        return User.objects.create_user(username=email, email=email, password=password)


class AuthForm(forms.Form):
    """Authentication by e-mail and password."""

    email = forms.EmailField(
        required=True,
        max_length=150,
        widget=forms.EmailInput(
            attrs={
                "class": "form-control mb-3",
                "placeholder": "Email",
                "autocomplete": "email",
            }
        ),
    )
    password = forms.CharField(
        required=True,
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control mb-3",
                "placeholder": "Пароль",
                "autocomplete": "current-password",
            }
        ),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = None

    def clean(self):
        cleaned_data = super().clean()
        email = cleaned_data.get("email")
        password = cleaned_data.get("password")

        if email and password:
            self.user = authenticate(username=email.lower(), password=password)
            if self.user is None:
                raise ValidationError("Неверный логин или пароль! Повторите попытку.")

        return cleaned_data
