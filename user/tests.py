from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

User = get_user_model()


class UserAuthTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="investor@example.com",
            email="investor@example.com",
            password="StrongPassword123!",
        )

    def test_registration_success(self):
        response = self.client.post(
            reverse("user:registration"),
            {
                "email": "newuser@example.com",
                "password1": "MySecurePassword123!",
                "password2": "MySecurePassword123!",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(User.objects.filter(email="newuser@example.com").exists())

    def test_registration_password_mismatch(self):
        response = self.client.post(
            reverse("user:registration"),
            {
                "email": "mismatch@example.com",
                "password1": "Pass111111!",
                "password2": "Pass222222!",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Введенные пароли не совпадают")
        self.assertFalse(User.objects.filter(email="mismatch@example.com").exists())

    def test_registration_duplicate_email(self):
        response = self.client.post(
            reverse("user:registration"),
            {
                "email": "INVESTOR@EXAMPLE.COM",
                "password1": "NewPassword123!",
                "password2": "NewPassword123!",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Данный e-mail уже зарегистрирован")

    def test_login_success_case_insensitive(self):
        response = self.client.post(
            reverse("user:auth"),
            {
                "email": "InVeStOr@ExAmPlE.cOm",
                "password": "StrongPassword123!",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("dashboard:index"))

    def test_login_invalid_password(self):
        response = self.client.post(
            reverse("user:auth"),
            {
                "email": "investor@example.com",
                "password": "WrongPassword!",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Неверный логин или пароль")

    def test_logout(self):
        self.client.login(username="investor@example.com", password="StrongPassword123!")
        response = self.client.get(reverse("user:logout"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("dashboard:index"))

    def test_html_crud_requires_authentication(self):
        # Anonymous user cannot access /create
        resp_create = self.client.get(reverse("dashboard:create"))
        self.assertEqual(resp_create.status_code, 302)

        # Logged-in user can access /create
        self.client.login(username="investor@example.com", password="StrongPassword123!")
        resp_create_auth = self.client.get(reverse("dashboard:create"))
        self.assertEqual(resp_create_auth.status_code, 200)
