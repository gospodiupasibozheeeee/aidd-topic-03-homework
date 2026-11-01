import uuid
from decimal import Decimal

from django.test import Client
from django.urls import reverse
from rest_framework.test import APIClient

from investing.models import (
    Notification,
    Portfolio,
    Strategy,
    Trade,
    WatchItem,
    Watchlist,
)
from investing.services.monitoring import save_watch_item

from .helpers import InvestingCase


class AccessTests(InvestingCase):
    def setUp(self):
        super().setUp()
        self.api = APIClient()
        self.api.force_authenticate(self.owner)

    def test_anonymous_private_endpoints_and_html_require_login(self):
        anonymous = APIClient()
        for resource in (
            "watchlists",
            "watch-items",
            "notifications",
            "portfolios",
            "strategies",
        ):
            self.assertEqual(anonymous.get(f"/api/v1/{resource}/").status_code, 403)
        response = self.client.get(reverse("investing:workspace"))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(reverse("user:auth")))

    def test_foreign_lists_items_notifications_portfolios_and_strategies_are_404(self):
        item = save_watch_item(
            self.owner, watchlist=self.watchlist, share=self.share, target=Decimal(100)
        )
        strategy = self.strategy()
        self.quote(100)
        notification = Notification.objects.get()
        self.api.force_authenticate(self.other)
        self.client.force_login(self.other)
        for resource, identifier in (
            ("watchlists", self.watchlist.pk),
            ("watch-items", item.pk),
            ("notifications", notification.pk),
            ("portfolios", self.portfolio.pk),
            ("strategies", strategy.pk),
        ):
            url = f"/api/v1/{resource}/{identifier}/"
            self.assertEqual(self.api.get(url).status_code, 404)
            self.assertEqual(
                self.api.patch(url, {}, format="json").status_code,
                404 if resource not in ("notifications",) else 405,
            )
            self.assertEqual(self.api.get(f"/api/v1/{resource}/").json()["count"], 0)
        for name, identifier in (
            ("watchlist", self.watchlist.pk),
            ("watch-item-edit", item.pk),
            ("portfolio", self.portfolio.pk),
            ("trade", self.portfolio.pk),
            ("strategy-edit", strategy.pk),
        ):
            self.assertEqual(
                self.client.get(
                    reverse(f"investing:{name}", args=[identifier])
                ).status_code,
                404,
            )
        self.assertEqual(
            self.api.post(f"/api/v1/notifications/{notification.pk}/read/").status_code,
            404,
        )
        self.assertEqual(
            self.api.get(f"/api/v1/portfolios/{self.portfolio.pk}/trades/").status_code,
            404,
        )
        self.assertEqual(
            self.api.get(f"/api/v1/strategies/{strategy.pk}/runs/").status_code, 404
        )

    def test_creation_cannot_reference_another_users_list_or_portfolio(self):
        self.api.force_authenticate(self.other)
        response = self.api.post(
            "/api/v1/watch-items/",
            {"watchlist": self.watchlist.pk, "share": self.share.pk},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        response = self.api.post(
            "/api/v1/strategies/",
            dict(
                portfolio=self.portfolio.pk,
                share=self.share.pk,
                name="Attack",
                quantity=1,
                buy_below="100",
                sell_above="120",
            ),
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(WatchItem.objects.exists())
        self.assertFalse(Strategy.objects.exists())

    def test_portfolio_money_and_currency_cannot_be_changed(self):
        url = f"/api/v1/portfolios/{self.portfolio.pk}/"
        self.assertEqual(
            self.api.patch(url, {"cash": "999999"}, format="json").status_code, 200
        )
        self.portfolio.refresh_from_db()
        self.assertEqual(self.portfolio.cash, Decimal(1000))
        for values in ({"currency": "usd"}, {"initial_cash": "999999"}):
            self.assertEqual(
                self.api.patch(url, values, format="json").status_code, 400
            )
        self.assertEqual(self.api.delete(url).status_code, 405)

    def test_trade_api_is_idempotent_read_only_and_reports_unknown_valuation(self):
        url = f"/api/v1/portfolios/{self.portfolio.pk}/trades/"
        data = {
            "share": self.share.pk,
            "side": "buy",
            "quantity": 2,
            "price": "100.123456789",
            "request_id": str(uuid.uuid4()),
        }
        response = self.api.post(url, data, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        repeated = self.api.post(url, data, format="json")
        self.assertEqual(repeated.status_code, 200)
        self.assertEqual(response.data["id"], repeated.data["id"])
        data["quantity"] = 3
        self.assertEqual(self.api.post(url, data, format="json").status_code, 409)
        response = self.api.get(url)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["price"], "100.123456789")
        summary = self.api.get(f"/api/v1/portfolios/{self.portfolio.pk}/").json()[
            "summary"
        ]
        self.assertIsNone(summary["total_value"])
        self.assertEqual(summary["holdings"][0]["ticker"], self.share.ticker)
        self.assertEqual(self.api.patch(url, data, format="json").status_code, 405)
        self.assertEqual(self.api.delete(url).status_code, 405)

    def test_notification_read_and_rule_revision_through_api(self):
        response = self.api.post(
            "/api/v1/watch-items/",
            {
                "watchlist": self.watchlist.pk,
                "share": self.share.pk,
                "target": "100",
                "direction": "gte",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        item_id = response.data["id"]
        self.quote(100)
        notification = Notification.objects.get()
        self.assertEqual(
            self.api.post(f"/api/v1/notifications/{notification.pk}/read/").status_code,
            200,
        )
        notification.refresh_from_db()
        self.assertIsNotNone(notification.read_at)
        self.assertEqual(
            self.api.patch(
                f"/api/v1/watch-items/{item_id}/", {"target": "110"}, format="json"
            ).status_code,
            200,
        )
        self.quote(110, 1)
        self.assertEqual(Notification.objects.count(), 2)
        self.assertEqual(
            self.api.delete(f"/api/v1/watchlists/{self.watchlist.pk}/").status_code, 204
        )
        self.assertEqual(Notification.objects.count(), 2)

    def test_strategy_api_creation_immutable_links_and_execution_journal(self):
        response = self.api.post(
            "/api/v1/strategies/",
            dict(
                portfolio=self.portfolio.pk,
                share=self.share.pk,
                name="API Cycle",
                quantity=1,
                buy_below="100",
                sell_above="120",
            ),
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        identifier = response.data["id"]
        self.quote(100)
        url = f"/api/v1/strategies/{identifier}/"
        self.assertEqual(self.api.get(url).data["next_action"], "sell")
        second = self.api.post(
            "/api/v1/portfolios/",
            dict(name="Second", currency="rub", initial_cash="100"),
            format="json",
        )
        self.assertEqual(second.status_code, 201, second.data)
        self.assertEqual(
            self.api.patch(
                url, {"portfolio": second.data["id"]}, format="json"
            ).status_code,
            400,
        )
        self.assertEqual(self.api.get(url + "runs/").data["count"], 1)
        self.assertEqual(
            self.api.patch(url, {"active": False}, format="json").status_code, 200
        )
        self.quote(120, 1)
        self.assertEqual(Trade.objects.count(), 1)
        self.assertEqual(self.api.delete(url).status_code, 204)
        self.assertEqual(self.portfolio.strategy_runs.count(), 1)
        self.assertEqual(
            self.api.get(f"/api/v1/portfolios/{self.portfolio.pk}/strategy-runs/").data[
                "count"
            ],
            1,
        )

    def test_private_pages_render_and_forms_validate(self):
        self.client.force_login(self.owner)
        strategy = self.strategy()
        item = save_watch_item(
            self.owner, watchlist=self.watchlist, share=self.share, target=Decimal(100)
        )
        self.quote(100)
        for name, args in (
            ("workspace", []),
            ("watchlist", [self.watchlist.pk]),
            ("watchlist-create", []),
            ("watch-item-edit", [item.pk]),
            ("notifications", []),
            ("portfolio", [self.portfolio.pk]),
            ("portfolio-create", []),
            ("trade", [self.portfolio.pk]),
            ("strategy-create", []),
            ("strategy-edit", [strategy.pk]),
        ):
            with self.subTest(name=name):
                self.assertEqual(
                    self.client.get(
                        reverse(f"investing:{name}", args=args)
                    ).status_code,
                    200,
                )
        response = self.client.post(
            reverse("investing:watchlist-create"), {"name": "Main"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].errors)
        response = self.client.post(
            reverse("investing:portfolio-create"),
            {"name": "New", "currency": "rub", "initial_cash": "-1"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].errors)

    def test_new_html_forms_work_end_to_end(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse("investing:watchlist-create"), {"name": "New list"}
        )
        self.assertEqual(response.status_code, 302)
        watchlist = Watchlist.objects.get(name="New list")
        self.assertEqual(
            self.client.post(
                reverse("investing:watchlist", args=[watchlist.pk]),
                {"share": self.share.pk, "direction": "gte", "target": "100"},
            ).status_code,
            302,
        )
        response = self.client.post(
            reverse("investing:portfolio-create"),
            {"name": "New portfolio", "currency": "RUB", "initial_cash": "1000"},
        )
        self.assertEqual(response.status_code, 302)
        portfolio = Portfolio.objects.get(name="New portfolio")
        trade = {
            "share": self.share.pk,
            "side": "buy",
            "quantity": 1,
            "price": "100",
            "request_id": str(uuid.uuid4()),
        }
        self.assertEqual(
            self.client.post(
                reverse("investing:trade", args=[portfolio.pk]), trade
            ).status_code,
            302,
        )
        strategy_data = dict(
            name="New rule",
            portfolio=portfolio.pk,
            share=self.share.pk,
            quantity=1,
            buy_below="100",
            sell_above="120",
            active=True,
        )
        self.assertEqual(
            self.client.post(
                reverse("investing:strategy-create"), strategy_data
            ).status_code,
            302,
        )
        strategy = Strategy.objects.get(name="New rule")
        strategy_data["name"] = "Edited"
        self.assertEqual(
            self.client.post(
                reverse("investing:strategy-edit", args=[strategy.pk]), strategy_data
            ).status_code,
            302,
        )
        self.quote(100)
        notification = Notification.objects.first()
        self.assertEqual(
            self.client.post(
                reverse("investing:notification-read", args=[notification.pk])
            ).status_code,
            302,
        )
        self.assertEqual(
            self.client.post(
                reverse("investing:strategy-delete", args=[strategy.pk])
            ).status_code,
            302,
        )
        self.assertEqual(
            self.client.post(
                reverse("investing:watchlist-delete", args=[watchlist.pk])
            ).status_code,
            302,
        )

    def test_personal_mutations_require_post_and_csrf(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.owner)
        self.assertEqual(
            client.post(
                reverse("investing:watchlist-create"), {"name": "Blocked"}
            ).status_code,
            403,
        )
        self.assertEqual(
            client.get(
                reverse("investing:watchlist-delete", args=[self.watchlist.pk])
            ).status_code,
            405,
        )
        client.get(reverse("investing:watchlist-create"))
        response = client.post(
            reverse("investing:watchlist-create"),
            {"name": "Allowed"},
            HTTP_X_CSRFTOKEN=client.cookies["csrftoken"].value,
        )
        self.assertEqual(response.status_code, 302)

    def test_share_with_financial_records_cannot_be_deleted(self):
        self.trade()
        self.client.force_login(self.owner)
        response = self.client.post(f"/delete/{self.share.pk}")
        self.assertContains(response, "не может быть удалена", status_code=409)
        self.assertEqual(
            self.api.delete(f"/api/v1/shares/{self.share.pk}/").status_code, 409
        )
        self.assertEqual(Trade.objects.count(), 1)
