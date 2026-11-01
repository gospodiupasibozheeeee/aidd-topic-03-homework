from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class AccountTests(TestCase):
    password = "Example-strong-pass-938!"

    def registration(self, **overrides):
        return {
            "email": "Mixed.Case@Example.com",
            "password1": self.password,
            "password2": self.password,
            **overrides,
        }

    def test_registration_normalizes_hashes_and_logs_in(self):
        self.assertRedirects(
            self.client.post(reverse("user:registration"), self.registration()), "/"
        )
        user = get_user_model().objects.get()
        self.assertEqual(user.username, "mixed.case@example.com")
        self.assertTrue(user.check_password(self.password))
        self.assertNotEqual(user.password, self.password)
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)

    def test_invalid_registration_never_crashes(self):
        for data in (
            {},
            self.registration(email="bad"),
            self.registration(password1=""),
            self.registration(password2=""),
        ):
            response = self.client.post(reverse("user:registration"), data)
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.context["form"].errors)
        self.assertFalse(get_user_model().objects.exists())

    def test_mismatched_and_weak_passwords_are_rejected(self):
        for data in (
            self.registration(password2="Different-password!"),
            self.registration(password1="123", password2="123"),
        ):
            response = self.client.post(reverse("user:registration"), data)
            self.assertTrue(response.context["form"].errors)
        self.assertFalse(get_user_model().objects.exists())

    def test_duplicate_email_ignores_case(self):
        get_user_model().objects.create_user(
            "oldname", "mixed.case@example.com", self.password
        )
        response = self.client.post(reverse("user:registration"), self.registration())
        self.assertIn("email", response.context["form"].errors)
        self.assertEqual(get_user_model().objects.count(), 1)

    def test_login_legacy_mixed_case_account(self):
        user = get_user_model().objects.create_user(
            "Mixed.Case@Example.com", "Mixed.Case@Example.com", self.password
        )
        self.assertRedirects(
            self.client.post(
                reverse("user:auth"),
                {"email": "MIXED.CASE@example.com", "password": self.password},
            ),
            "/",
        )
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)

    def test_missing_invalid_wrong_and_inactive_login(self):
        get_user_model().objects.create_user(
            "inactive@example.com", password=self.password, is_active=False
        )
        for data in (
            {},
            {"email": "bad", "password": "123"},
            {"email": "none@example.com", "password": "wrong"},
            {"email": "inactive@example.com", "password": self.password},
        ):
            response = self.client.post(reverse("user:auth"), data)
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.context["form"].errors)
            self.assertNotIn("_auth_user_id", self.client.session)

    def test_logout_get_confirms_post_logs_out(self):
        self.client.force_login(
            get_user_model().objects.create_user("logout@example.com")
        )
        self.assertEqual(self.client.get(reverse("user:logout")).status_code, 200)
        self.assertIn("_auth_user_id", self.client.session)
        self.assertRedirects(self.client.post(reverse("user:logout")), "/")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_canonical_and_legacy_urls(self):
        self.assertEqual(reverse("user:auth"), "/user/login/")
        for path in (
            "/user/login/",
            "/userlogin/",
            "/user/registration/",
            "/userregistration/",
            "/user/logout/",
            "/userlogout/",
        ):
            self.assertEqual(self.client.get(path).status_code, 200)

    def test_csrf_protects_all_account_forms(self):
        client = Client(enforce_csrf_checks=True)
        for name in ("auth", "registration", "logout"):
            self.assertEqual(client.post(reverse(f"user:{name}"), {}).status_code, 403)

    def test_login_returns_to_private_page_and_rejects_external_redirect(self):
        get_user_model().objects.create_user(
            "redirect@example.com", password=self.password
        )
        for destination, expected in (
            ("/workspace/", "/workspace/"),
            ("https://example.org/", "/"),
        ):
            self.client.logout()
            response = self.client.post(
                reverse("user:auth"),
                {
                    "email": "redirect@example.com",
                    "password": self.password,
                    "next": destination,
                },
            )
            self.assertRedirects(response, expected)
