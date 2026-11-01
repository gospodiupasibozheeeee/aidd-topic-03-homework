from decimal import Decimal
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from dashboard.models import Share

User = get_user_model()


class DashboardTests(APITestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user(
            username="investor@example.com",
            email="investor@example.com",
            password="StrongPassword123!",
        )
        self.client.force_authenticate(user=self.user)

        self.apple_share = Share.objects.create(
            figi="BBG000B9XRY4",
            isin="US0378331005",
            name="Apple",
            ticker="AAPL",
            currency="usd",
            uid="a9eb4238-eba9-488c-b102-b6140fd08e38",
            last_price=Decimal("100.50"),
            is_trend_high=True,
        )

        self.second_company = {
            "figi": "BBG000B9XRY5",
            "isin": "US0378331004",
            "name": "Company_test",
            "ticker": "TESTTEST",
            "currency": "usd",
            "uid": "a9eb4238-eba9-488c-b102-b6140fd08e39",
            "last_price": Decimal("1.50"),
            "is_trend_high": False,
        }

    def test_share_list_html(self):
        response = self.client.get(reverse("dashboard:index"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertContains(response, "AAPL")
        self.assertContains(response, "Apple")

    def test_share_detail_html(self):
        response = self.client.get(reverse("dashboard:detail", kwargs={"pk": self.apple_share.id}))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertContains(response, "Apple")

    def test_share_detail_html_not_found(self):
        response = self.client.get(reverse("dashboard:detail", kwargs={"pk": 99999}))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_share_list(self):
        response = self.client.get("/api/v1/shares/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)
        apple_share = response.json().get("results")[0]
        self.assertEqual(apple_share["id"], self.apple_share.id)
        self.assertEqual(apple_share["figi"], self.apple_share.figi)
        self.assertEqual(apple_share["isin"], self.apple_share.isin)
        self.assertEqual(apple_share["name"], self.apple_share.name)
        self.assertEqual(apple_share["ticker"], self.apple_share.ticker)
        self.assertEqual(apple_share["currency"], self.apple_share.currency)
        self.assertEqual(apple_share["uid"], self.apple_share.uid)

    def test_share_detail(self):
        response = self.client.get("/api/v1/shares/")
        share_detail = response.json().get("results")[0]
        response = self.client.get(f"/api/v1/shares/{share_detail['id']}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_share_detail_invalid(self):
        response = self.client.get("/api/v1/shares/99999/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_share_update(self):
        response = self.client.get("/api/v1/shares/")
        share_detail = response.json().get("results")[0]
        response = self.client.put(
            f"/api/v1/shares/{share_detail['id']}/",
            {
                "id": share_detail["id"],
                "figi": self.apple_share.figi,
                "isin": self.apple_share.isin,
                "name": f"{self.apple_share.name}_test",
                "ticker": self.apple_share.ticker,
                "currency": self.apple_share.currency,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        body = response.json()
        self.assertEqual(body["figi"], self.apple_share.figi)
        self.assertEqual(body["name"], f"{self.apple_share.name}_test")

    def test_share_update_invalid(self):
        response = self.client.get("/api/v1/shares/")
        share_detail = response.json().get("results")[0]
        response = self.client.put(
            f"/api/v1/shares/{share_detail['id']}/",
            {
                "figi": self.apple_share.figi,
                "name": f"{self.apple_share.name}_test",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_share_create(self):
        response = self.client.post(
            "/api/v1/shares/", self.second_company, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        body = response.json()
        self.assertEqual(body["figi"], self.second_company["figi"])
        self.assertEqual(body["name"], self.second_company["name"])
        self.assertEqual(body["ticker"], self.second_company["ticker"])

        response = self.client.get("/api/v1/shares/")
        self.assertEqual(len(response.data["results"]), 2)

    def test_share_create_without_uid_auto_generates(self):
        data = {
            "figi": "BBG000B9XRY9",
            "isin": "US0378331099",
            "name": "AutoUID Company",
            "ticker": "AUTOUID",
            "currency": "usd",
        }
        response = self.client.post("/api/v1/shares/", data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(len(response.data.get("uid", "")) > 0)

    def test_share_create_invalid(self):
        response = self.client.post(
            "/api/v1/shares/", {"figi": "BBG000B9XRY5"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_share_delete(self):
        response = self.client.get("/api/v1/shares/")
        share_detail = response.json().get("results")[0]
        response = self.client.delete(f"/api/v1/shares/{share_detail['id']}/")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        response = self.client.get("/api/v1/shares/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 0)

    def test_share_delete_invalid(self):
        response = self.client.delete("/api/v1/shares/99999/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_unauthenticated_api_mutations_are_forbidden(self):
        self.client.force_authenticate(user=None)
        # GET is allowed
        get_resp = self.client.get("/api/v1/shares/")
        self.assertEqual(get_resp.status_code, status.HTTP_200_OK)

        # POST is forbidden for anonymous users
        post_resp = self.client.post("/api/v1/shares/", self.second_company, format="json")
        self.assertEqual(post_resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_share_filtering_and_ordering(self):
        response = self.client.get("/api/v1/shares/?ticker=AAPL")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)

        response_none = self.client.get("/api/v1/shares/?ticker=NONEXISTENT")
        self.assertEqual(response_none.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response_none.data["results"]), 0)

    def test_update_last_price_task(self):
        from unittest.mock import patch
        from django.utils import timezone
        from dashboard.tasks import update_last_price

        old_updated_at = self.apple_share.updated_at
        mock_now = timezone.now()

        # Тест роста цены: 100.50 -> 120.75 => is_trend_high=True
        with patch("dashboard.tasks.get_batch_market_data") as mock_batch:
            mock_batch.return_value = {
                self.apple_share.id: (Decimal("120.75"), mock_now)
            }
            update_last_price()

        self.apple_share.refresh_from_db()
        self.assertEqual(self.apple_share.last_price, Decimal("120.75"))
        self.assertTrue(self.apple_share.is_trend_high)
        self.assertIsNotNone(self.apple_share.updated_at)

        # Тест падения цены: 120.75 -> 95.20 => is_trend_high=False
        with patch("dashboard.tasks.get_batch_market_data") as mock_batch:
            mock_batch.return_value = {
                self.apple_share.id: (Decimal("95.20"), mock_now)
            }
            update_last_price()

        self.apple_share.refresh_from_db()
        self.assertEqual(self.apple_share.last_price, Decimal("95.20"))
        self.assertFalse(self.apple_share.is_trend_high)
