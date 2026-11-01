from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from dashboard.models import Share
from dashboard.services.graph import get_graph
from dashboard.services.market_data import MarketDataError
from dashboard.services.tinkoff import quotation_to_decimal
from dashboard.tasks import update_last_price

User = get_user_model()


def make_share(**overrides):
    data = {
        "figi": "BBG000B9XRY4",
        "isin": "US0378331005",
        "name": "Apple Inc.",
        "ticker": "AAPL",
        "currency": "USD",
        "last_price": Decimal("100.50"),
        "is_trend_high": True,
    }
    data.update(overrides)
    return Share.objects.create(**data)


class ShareModelTests(TestCase):
    def test_uid_is_generated_automatically(self):
        share = make_share()
        self.assertTrue(share.uid)
        self.assertNotEqual(share.uid, "")

    def test_str_contains_ticker_and_name(self):
        share = make_share()
        self.assertIn("AAPL", str(share))
        self.assertIn("Apple", str(share))

    def test_price_as_decimal(self):
        share = make_share(last_price=Decimal("123.456789"))
        self.assertEqual(share.price_as_decimal, Decimal("123.456789"))

    def test_quotation_conversion_uses_nano(self):
        quotation = SimpleNamespace(units=100, nano=500_000_000)
        self.assertEqual(quotation_to_decimal(quotation), Decimal("100.5"))


class GraphServiceTests(TestCase):
    @patch("dashboard.services.graph.get_candles")
    def test_graph_uses_close_price_with_nano(self, get_candles):
        now = timezone.now()
        get_candles.return_value = [
            SimpleNamespace(
                time=now,
                close=SimpleNamespace(units=100, nano=500_000_000),
            )
        ]
        share = Share(
            figi="FIGI",
            isin="ISIN",
            name="Test",
            ticker="TST",
            currency="RUB",
        )
        html = get_graph(share)
        self.assertIn("<div", html)
        self.assertIn("100.5", html)
        get_candles.assert_called_once_with(share, days=180)


class ShareFormTests(TestCase):
    def test_form_excludes_generated_fields(self):
        from dashboard.forms import ShareModelForm

        form = ShareModelForm()
        self.assertNotIn("uid", form.fields)
        self.assertNotIn("updated_at", form.fields)
        self.assertIn("figi", form.fields)

    def test_negative_price_is_rejected(self):
        from dashboard.forms import ShareModelForm

        form = ShareModelForm(
            data={
                "figi": "BBG000B9XRY6",
                "isin": "US0378331006",
                "name": "Test",
                "ticker": "TEST",
                "currency": "USD",
                "last_price": "-1",
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("last_price", form.errors)


class ShareHTMLViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="user@example.com",
            email="user@example.com",
            password="StrongPass123!",
        )
        self.share = make_share()

    def test_catalogue_is_public(self):
        response = self.client.get(reverse("dashboard:index"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "AAPL")
        self.assertContains(response, "Apple Inc.")

    def test_empty_catalogue_message(self):
        Share.objects.all().delete()
        response = self.client.get(reverse("dashboard:index"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Акций еще нет")

    @patch("dashboard.views.get_graph", return_value="<div id='chart'></div>")
    def test_detail_is_public_and_renders_chart(self, get_graph):
        response = self.client.get(reverse("dashboard:detail", args=[self.share.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Apple Inc.")
        self.assertContains(response, "chart")
        get_graph.assert_called_once()

    def test_missing_detail_returns_404(self):
        response = self.client.get(reverse("dashboard:detail", args=[99999]))
        self.assertEqual(response.status_code, 404)

    @patch("dashboard.views.get_graph", side_effect=MarketDataError("нет токена"))
    def test_chart_error_is_graceful(self, _get_graph):
        response = self.client.get(reverse("dashboard:detail", args=[self.share.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "нет токена")

    def test_anonymous_create_redirects(self):
        response = self.client.get(reverse("dashboard:create"))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith("/"))

    def test_authenticated_create_saves_share(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("dashboard:create"),
            {
                "figi": "BBG000B9XRY5",
                "isin": "US0378331004",
                "name": "Microsoft",
                "ticker": "MSFT",
                "currency": "USD",
                "last_price": "250.25",
                "is_trend_high": "on",
            },
        )
        self.assertEqual(response.status_code, 302)
        created = Share.objects.get(figi="BBG000B9XRY5")
        self.assertEqual(created.last_price, Decimal("250.25"))
        self.assertTrue(created.uid)

    def test_authenticated_update_changes_share(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("dashboard:update", args=[self.share.pk]),
            {
                "figi": self.share.figi,
                "isin": self.share.isin,
                "name": "Apple Updated",
                "ticker": self.share.ticker,
                "currency": self.share.currency,
                "last_price": "111.11",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.share.refresh_from_db()
        self.assertEqual(self.share.name, "Apple Updated")
        self.assertEqual(self.share.last_price, Decimal("111.11"))

    def test_authenticated_delete_removes_share(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("dashboard:delete", args=[self.share.pk]))
        self.assertEqual(response.status_code, 200)
        response = self.client.post(reverse("dashboard:delete", args=[self.share.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Share.objects.filter(pk=self.share.pk).exists())

    def test_trailing_slash_create_redirects(self):
        response = self.client.get("/create/")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/create")


class AuthenticationViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="auth@example.com",
            email="auth@example.com",
            password="StrongPass123!",
        )

    def test_login_is_case_insensitive_for_email(self):
        response = self.client.post(
            reverse("user:auth"),
            {"email": "AUTH@EXAMPLE.COM", "password": "StrongPass123!"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("_auth_user_id", self.client.session)

    def test_login_with_wrong_password_shows_error(self):
        response = self.client.post(
            reverse("user:auth"),
            {"email": self.user.email, "password": "wrong"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Неверный логин или пароль")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_registration_creates_user_and_logs_in(self):
        response = self.client.post(
            reverse("user:registration"),
            {
                "email": "new@example.com",
                "password1": "AnotherPass123!",
                "password2": "AnotherPass123!",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(User.objects.filter(email="new@example.com").exists())
        self.assertIn("_auth_user_id", self.client.session)

    def test_registration_rejects_mismatched_passwords(self):
        response = self.client.post(
            reverse("user:registration"),
            {
                "email": "new@example.com",
                "password1": "AnotherPass123!",
                "password2": "DifferentPass123!",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(email="new@example.com").exists())
        self.assertContains(response, "не совпадают")

    def test_registration_rejects_duplicate_email(self):
        response = self.client.post(
            reverse("user:registration"),
            {
                "email": "AUTH@example.com",
                "password1": "AnotherPass123!",
                "password2": "AnotherPass123!",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            User.objects.filter(email__iexact="auth@example.com").count(), 1
        )

    def test_registration_rejects_weak_password(self):
        response = self.client.post(
            reverse("user:registration"),
            {
                "email": "weak@example.com",
                "password1": "password",
                "password2": "password",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(email="weak@example.com").exists())

    def test_logout_requires_post(self):
        self.client.force_login(self.user)
        self.client.get(reverse("user:logout"))
        self.assertIn("_auth_user_id", self.client.session)

        self.client.post(reverse("user:logout"))
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_legacy_auth_url_redirects(self):
        response = self.client.get("/userlogin/")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/user/login/")


class ShareAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="api@example.com",
            email="api@example.com",
            password="StrongPass123!",
        )
        self.share = make_share()
        self.client = APIClient()

    def test_list_is_public_and_contains_uid(self):
        response = self.client.get("/api/v1/shares/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertIn("uid", response.data["results"][0])

    def test_anonymous_create_is_forbidden(self):
        response = self.client.post(
            "/api/v1/shares/",
            {
                "figi": "BBG000B9XRY5",
                "isin": "US0378331004",
                "name": "Microsoft",
                "ticker": "MSFT",
                "currency": "USD",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_anonymous_update_and_delete_are_forbidden(self):
        response = self.client.patch(
            f"/api/v1/shares/{self.share.pk}/",
            {"name": "Hacked"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        response = self.client.delete(f"/api/v1/shares/{self.share.pk}/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_authenticated_create_generates_uid_and_allows_second_record(self):
        self.client.force_authenticate(user=self.user)
        payload = {
            "figi": "BBG000B9XRY5",
            "isin": "US0378331004",
            "name": "Microsoft",
            "ticker": "MSFT",
            "currency": "USD",
            "uid": "client-supplied-uid",
        }
        response = self.client.post("/api/v1/shares/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertNotEqual(response.data["uid"], "client-supplied-uid")

        payload["figi"] = "BBG000B9XRY6"
        payload["isin"] = "US0378331006"
        payload["ticker"] = "GOOG"
        response = self.client.post("/api/v1/shares/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Share.objects.count(), 3)

    def test_authenticated_update_and_delete(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.patch(
            f"/api/v1/shares/{self.share.pk}/",
            {"name": "Apple Updated"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.share.refresh_from_db()
        self.assertEqual(self.share.name, "Apple Updated")

        response = self.client.delete(f"/api/v1/shares/{self.share.pk}/")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Share.objects.filter(pk=self.share.pk).exists())

    def test_filter_search_ordering_and_pagination(self):
        make_share(
            figi="BBG000B9XRY5",
            isin="US0378331004",
            name="Microsoft",
            ticker="MSFT",
            currency="USD",
        )
        response = self.client.get("/api/v1/shares/", {"name": "Microsoft"})
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["ticker"], "MSFT")

        response = self.client.get("/api/v1/shares/", {"search": "app"})
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["ticker"], "AAPL")

        response = self.client.get("/api/v1/shares/", {"ordering": "-name"})
        self.assertEqual(response.data["results"][0]["name"], "Microsoft")

        response = self.client.get("/api/v1/shares/", {"limit": 1})
        self.assertEqual(len(response.data["results"]), 1)
        self.assertIsNotNone(response.data["next"])

    def test_missing_detail_returns_404(self):
        response = self.client.get("/api/v1/shares/99999/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class UpdateLastPriceTaskTests(TestCase):
    def setUp(self):
        self.share = make_share(last_price=Decimal("100.0"), is_trend_high=True)

    @patch("dashboard.tasks.get_last_prices")
    def test_updates_price_trend_and_updated_at(self, get_last_prices):
        now = timezone.now()
        get_last_prices.return_value = {
            self.share.figi: (Decimal("101.5"), now),
        }
        result = update_last_price()
        self.assertEqual(result, 1)
        self.share.refresh_from_db()
        self.assertEqual(self.share.last_price, Decimal("101.5"))
        self.assertTrue(self.share.is_trend_high)
        self.assertIsNotNone(self.share.updated_at)

    @patch("dashboard.tasks.get_last_prices")
    def test_lower_price_marks_trend_as_falling(self, get_last_prices):
        get_last_prices.return_value = {
            self.share.figi: (Decimal("99.0"), timezone.now()),
        }
        update_last_price()
        self.share.refresh_from_db()
        self.assertFalse(self.share.is_trend_high)

    @patch("dashboard.tasks.get_last_prices", side_effect=MarketDataError("down"))
    def test_api_error_does_not_crash(self, _get_last_prices):
        result = update_last_price()
        self.assertEqual(result, 0)
        self.share.refresh_from_db()
        self.assertEqual(self.share.last_price, Decimal("100.0"))


class AddSharesCommandTests(TestCase):
    @patch("dashboard.management.commands.add_shares.tinkoff_client")
    def test_import_creates_and_updates_without_duplicates(self, tinkoff_client):
        instrument = SimpleNamespace(
            figi="BBG000B9XRY7",
            isin="US0378331007",
            name="Imported",
            ticker="IMP",
            currency="USD",
            uid="uid-imported-1",
        )
        client = MagicMock()
        client.instruments.shares.return_value = SimpleNamespace(
            instruments=[instrument]
        )
        context = MagicMock()
        context.__enter__.return_value = client
        context.__exit__.return_value = False
        tinkoff_client.return_value = context

        call_command("add_shares")
        self.assertEqual(Share.objects.filter(figi=instrument.figi).count(), 1)

        instrument.name = "Imported Updated"
        call_command("add_shares")
        self.assertEqual(Share.objects.filter(figi=instrument.figi).count(), 1)
        self.assertEqual(
            Share.objects.get(figi=instrument.figi).name,
            "Imported Updated",
        )
