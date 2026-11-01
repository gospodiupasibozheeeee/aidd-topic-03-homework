from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.urls import reverse
from django.utils import timezone

from investing.forms import HistoryRangeForm
from investing.services.history import history_data

from .helpers import InvestingCase


class HistoryTests(InvestingCase):
    def setUp(self):
        super().setUp()
        # Keep all same-day samples within the selected UTC date at midnight too.
        self.time = timezone.now().replace(hour=12, minute=0, second=0, microsecond=0)

    def test_inclusive_dates_summary_and_daily_aggregation(self):
        self.quote(100, -86400)
        self.quote(120, -86300)
        self.quote(140, 0)
        records, summary, daily = history_data(
            self.share, (self.time - timedelta(days=1)).date(), self.time.date()
        )
        self.assertEqual(summary["count"], 3)
        self.assertEqual(summary["absolute_change"], Decimal(40))
        self.assertEqual(summary["percent_change"], Decimal(40))
        self.assertEqual([row["price"] for row in daily], [Decimal(110), Decimal(140)])
        _, summary, _ = history_data(self.share, self.time.date(), self.time.date())
        self.assertEqual(summary["count"], 1)

    def test_zero_initial_price_and_empty_range(self):
        self.quote(0)
        self.quote(10, 1)
        _, summary, _ = history_data(self.share, self.time.date(), self.time.date())
        self.assertEqual(summary["absolute_change"], Decimal(10))
        self.assertIsNone(summary["percent_change"])
        _, summary, daily = history_data(
            self.share,
            (self.time + timedelta(days=1)).date(),
            (self.time + timedelta(days=1)).date(),
        )
        self.assertEqual(summary["count"], 0)
        self.assertIsNone(summary["first_price"])
        self.assertEqual(daily, [])

    def test_currency_change_does_not_create_mixed_currency_percentage(self):
        self.quote(100)
        self.share.currency = "usd"
        self.share.save()
        self.quote(2, 1)
        _, summary, daily = history_data(self.share, self.time.date(), self.time.date())
        self.assertFalse(summary["comparable"])
        self.assertIsNone(summary["absolute_change"])
        self.assertIsNone(summary["percent_change"])
        self.assertEqual({point["currency"] for point in daily}, {"rub", "usd"})

    def test_public_history_uses_local_data_only_and_paginates(self):
        self.quote("100.123456789")
        self.quote(120, 1)
        with patch(
            "dashboard.services.client.requests.Session.post",
            side_effect=AssertionError("No network"),
        ):
            response = self.client.get(
                reverse("investing:history", args=[self.share.pk])
            )
            self.assertContains(response, "Plotly.newPlot")
            response = self.client.get(
                f"/api/v1/shares/{self.share.pk}/history/", {"limit": 1}
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 2)
        self.assertEqual(len(response.json()["results"]), 1)
        self.assertEqual(response.json()["results"][0]["price"], "100.123456789")
        self.assertIn("daily", response.json())
        self.assertIsNotNone(response.json()["next"])

    def test_invalid_dates_and_reversed_period_are_400(self):
        for parameters in (
            {"start": "bad"},
            {"start": "2026-02-02", "end": "2026-02-01"},
        ):
            self.assertEqual(
                self.client.get(
                    reverse("investing:history", args=[self.share.pk]), parameters
                ).status_code,
                400,
            )
            self.assertEqual(
                self.client.get(
                    f"/api/v1/shares/{self.share.pk}/history/", parameters
                ).status_code,
                400,
            )
        self.assertTrue(HistoryRangeForm({"end": "0001-01-01"}).is_valid())
        self.assertTrue(HistoryRangeForm({"end": "9999-12-31"}).is_valid())
