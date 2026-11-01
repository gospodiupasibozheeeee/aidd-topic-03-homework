from django import forms
from django.contrib.auth import authenticate, password_validation
from django.core.exceptions import ValidationError

from .models import User


class EmailForm(forms.Form):
    email = forms.EmailField(max_length=150, label="Email")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control my-3 p-4"

    def clean_email(self):
        return self.cleaned_data["email"].strip().lower()


class RegistrationForm(EmailForm):
    password1 = forms.CharField(label="Пароль", strip=False, widget=forms.PasswordInput)
    password2 = forms.CharField(
        label="Повторите пароль", strip=False, widget=forms.PasswordInput
    )

    def clean_email(self):
        email = super().clean_email()
        if (
            User.objects.filter(email__iexact=email).exists()
            or User.objects.filter(username__iexact=email).exists()
        ):
            raise ValidationError(
                "Данный e-mail уже зарегистрирован! Воспользуйтесь формой входа."
            )
        return email

    def clean(self):
        cleaned = super().clean()
        first, second = cleaned.get("password1"), cleaned.get("password2")
        if first and second and first != second:
            self.add_error("password2", "Введенные пароли не совпадают")
        if first:
            email = cleaned.get("email", "")
            password_validation.validate_password(
                first, User(username=email, email=email)
            )
        return cleaned

    def save(self):
        email = self.cleaned_data["email"]
        return User.objects.create_user(
            username=email, email=email, password=self.cleaned_data["password1"]
        )


class AuthForm(EmailForm):
    password = forms.CharField(label="Пароль", strip=False, widget=forms.PasswordInput)

    def __init__(self, *args, request=None, **kwargs):
        self.request = request
        self.user = None
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("email") and cleaned.get("password"):
            self.user = authenticate(
                self.request, username=cleaned["email"], password=cleaned["password"]
            )
            if self.user is None:
                raise ValidationError("Неверный логин или пароль! Повторите попытку.")
        return cleaned
