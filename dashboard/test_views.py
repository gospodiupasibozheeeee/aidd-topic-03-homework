from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from rest_framework.test import APIClient, APITestCase

from .models import Share
from .services.client import MarketDataError
from .test_helpers import make_share


class HTMLTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("html@example.com")
        self.share = make_share()

    def test_public_list_and_empty_state(self):
        response = self.client.get("/")
        self.assertContains(response, self.share.ticker)
        self.assertNotContains(response, 'href="/create"')
        Share.objects.all().delete()
        self.assertContains(self.client.get("/"), "Акций еще нет")

    def test_sorting_and_pagination(self):
        for number in range(2, 102):
            make_share(number)
        response = self.client.get("/")
        self.assertEqual(len(response.context["share_list"]), 100)
        names = [share.name for share in response.context["share_list"]]
        self.assertEqual(names, sorted(names))
        self.assertEqual(len(self.client.get("/?page=2").context["share_list"]), 1)

    def test_anonymous_changes_redirect(self):
        for path in ("/create", f"/update/{self.share.pk}", f"/delete/{self.share.pk}"):
            self.assertRedirects(self.client.get(path), "/")
            self.assertRedirects(self.client.post(path, {}), "/")
        self.assertEqual(Share.objects.count(), 1)

    def test_authenticated_html_crud(self):
        self.client.force_login(self.user)
        data = dict(
            figi="SECOND",
            isin="ISIN2",
            name="New share",
            ticker="SECOND",
            currency="rub",
            uid="second-uid",
            last_price="123.456789123",
        )
        self.assertRedirects(self.client.post("/create", data), "/")
        share = Share.objects.get(figi="SECOND")
        self.assertEqual(share.last_price, Decimal("123.456789123"))
        data["name"] = "Changed share"
        self.assertRedirects(self.client.post(f"/update/{share.pk}", data), "/")
        share.refresh_from_db()
        self.assertEqual(share.name, "Changed share")
        self.assertContains(self.client.get(f"/delete/{share.pk}"), "Changed share")
        self.assertTrue(Share.objects.filter(pk=share.pk).exists())
        self.assertRedirects(self.client.post(f"/delete/{share.pk}"), "/")
        self.assertFalse(Share.objects.filter(pk=share.pk).exists())

    def test_invalid_or_duplicate_html_form(self):
        self.client.force_login(self.user)
        for data in (
            {"figi": "ONLYFIGI"},
            dict(
                figi=self.share.figi,
                isin="SECOND",
                name="Duplicate",
                ticker="SECOND",
                currency="rub",
                uid="second-uid",
            ),
        ):
            response = self.client.post("/create", data)
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.context["form"].errors)
        self.assertEqual(Share.objects.count(), 1)

    def test_missing_detail_is_404(self):
        self.assertEqual(self.client.get("/999999").status_code, 404)

    @patch("dashboard.views.get_graph", side_effect=MarketDataError("offline"))
    def test_detail_survives_provider_failure(self, graph):
        with self.assertLogs("main", level="WARNING"):
            response = self.client.get(f"/{self.share.pk}")
        self.assertContains(response, self.share.name)
        self.assertContains(response, "Рыночные данные временно недоступны")

    @patch("dashboard.views.get_graph", return_value="<div>Test graph</div>")
    def test_detail_renders_graph(self, graph):
        self.assertContains(
            self.client.get(f"/{self.share.pk}"), "<div>Test graph</div>", html=True
        )

    @patch("dashboard.views.get_graph", return_value="")
    def test_empty_candles_message(self, graph):
        self.assertContains(self.client.get(f"/{self.share.pk}"), "нет рыночных данных")

    def test_neutral_trend_is_not_decline(self):
        response = self.client.get("/")
        self.assertNotContains(response, "palevioletred")
        self.assertNotContains(response, "mediumseagreen")

    def test_csrf_protects_html_changes(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        self.assertEqual(client.post(f"/delete/{self.share.pk}").status_code, 403)
        client.get(f"/delete/{self.share.pk}")
        self.assertEqual(
            client.post(
                f"/delete/{self.share.pk}",
                HTTP_X_CSRFTOKEN=client.cookies["csrftoken"].value,
            ).status_code,
            302,
        )

    def test_admin_list_search_and_form(self):
        self.user.is_staff = self.user.is_superuser = True
        self.user.save()
        self.client.force_login(self.user)
        path = reverse("admin:dashboard_share_changelist")
        self.assertContains(self.client.get(path), self.share.figi)
        self.assertContains(
            self.client.get(path, {"q": self.share.ticker}), self.share.name
        )
        self.assertNotContains(self.client.get(path, {"q": "absent"}), self.share.name)
        self.assertContains(
            self.client.get(
                reverse("admin:dashboard_share_change", args=[self.share.pk])
            ),
            'name="uid"',
        )


class APIRegressionTests(APITestCase):
    def setUp(self):
        self.share = make_share(last_price=Decimal("100.500000001"), name="Apple")
        self.user = get_user_model().objects.create_user("api@example.com")
        self.url = "/api/v1/shares/"

    def data(self, number):
        return dict(
            figi=f"FIGI{number}",
            isin=f"ISIN{number}",
            name=f"Share {number}",
            ticker=f"TEST{number}",
            currency="rub",
            uid=f"uid-{number}",
        )

    def test_public_read_and_anonymous_write_denial(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.json()["results"][0]["last_price"], float)
        detail = f"{self.url}{self.share.pk}/"
        for method, path, data in (
            ("post", self.url, self.data(2)),
            ("put", detail, self.data(1)),
            ("patch", detail, {"name": "Changed"}),
            ("delete", detail, {}),
        ):
            self.assertEqual(
                getattr(self.client, method)(path, data, format="json").status_code, 403
            )
        self.assertEqual(Share.objects.count(), 1)

    def test_two_creates_keep_distinct_uids(self):
        self.client.force_authenticate(self.user)
        for number in (2, 3):
            response = self.client.post(self.url, self.data(number), format="json")
            self.assertEqual(response.status_code, 201, response.data)
            self.assertEqual(
                Share.objects.get(figi=f"FIGI{number}").uid, f"uid-{number}"
            )

    def test_missing_duplicate_uid_and_duplicate_ticker_are_400(self):
        self.client.force_authenticate(self.user)
        for changes in (
            {"uid": ""},
            {"uid": self.share.uid},
            {"ticker": self.share.ticker},
        ):
            data = {**self.data(2), **changes}
            self.assertEqual(
                self.client.post(self.url, data, format="json").status_code, 400
            )
        data = self.data(2)
        del data["uid"]
        self.assertEqual(
            self.client.post(self.url, data, format="json").status_code, 400
        )

    def test_patch_preserves_omitted_uid(self):
        self.client.force_authenticate(self.user)
        response = self.client.patch(
            f"{self.url}{self.share.pk}/", {"name": "Changed"}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.share.refresh_from_db()
        self.assertEqual((self.share.uid, self.share.name), ("uid-1", "Changed"))

    def test_filters_search_sort_limit_and_offset(self):
        make_share(2, name="Beta")
        for params in ({"ticker": "TEST1"}, {"name": "Apple"}, {"search": "^app"}):
            response = self.client.get(self.url, params)
            self.assertEqual(response.data["count"], 1)
            self.assertEqual(response.data["results"][0]["name"], "Apple")
        response = self.client.get(
            self.url, {"ordering": "-name", "limit": 1, "offset": 1}
        )
        self.assertEqual(response.data["count"], 2)
        self.assertEqual(response.data["results"][0]["name"], "Apple")
        self.assertIn("previous", response.data)

    def test_invalid_regex_is_400(self):
        self.assertEqual(self.client.get(self.url, {"search": "["}).status_code, 400)

    def test_session_api_requires_csrf(self):
        client = APIClient(enforce_csrf_checks=True)
        client.force_login(self.user)
        self.assertEqual(
            client.post(self.url, self.data(2), format="json").status_code, 403
        )
        client.get("/create")
        self.assertEqual(
            client.post(
                self.url,
                self.data(2),
                format="json",
                HTTP_X_CSRFTOKEN=client.cookies["csrftoken"].value,
            ).status_code,
            201,
        )
