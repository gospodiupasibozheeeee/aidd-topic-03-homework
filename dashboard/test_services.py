from datetime import timedelta
from decimal import Decimal
from io import StringIO
from unittest.mock import patch

import requests
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone

from .models import Share
from .services.client import (
    MarketDataClient,
    MarketDataError,
    quotation_time,
    quotation_to_decimal,
)
from .services.graph import get_graph
from .services.market_data import get_last_data
from .tasks import update_last_price
from .test_helpers import make_share


@override_settings(TINKOFF_TOKEN="test-token", TINKOFF_CA_BUNDLE="", TINKOFF_TIMEOUT=3)
class ClientTests(SimpleTestCase):
    def test_decimal_precision_and_negative_price(self):
        self.assertEqual(
            quotation_to_decimal({"units": "123", "nano": 456789123}),
            Decimal("123.456789123"),
        )
        self.assertEqual(
            quotation_to_decimal({"units": "-1", "nano": -500000000}), Decimal("-1.5")
        )

    def test_invalid_quotes_and_times_are_domain_errors(self):
        for value in (
            {},
            None,
            {"units": "NaN"},
            {"units": "bad"},
            {"units": "1000000000000000"},
        ):
            with self.subTest(value=value), self.assertRaises(MarketDataError):
                quotation_to_decimal(value)
        for value in (None, "bad", "2026-01-01T00:00:00"):
            with self.subTest(value=value), self.assertRaises(MarketDataError):
                quotation_time(value)

    @patch("dashboard.services.client.requests.Session")
    def test_rest_payload_auth_timeout_tls_and_cleanup(self, session):
        session.return_value.post.return_value.json.return_value = {"lastPrices": []}
        with MarketDataClient() as client:
            self.assertEqual(client.last_prices(["FIGI"]), [])
        args, kwargs = session.return_value.post.call_args
        self.assertTrue(args[0].endswith("MarketDataService/GetLastPrices"))
        self.assertEqual(kwargs["json"], {"instrumentId": ["FIGI"]})
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer test-token")
        self.assertEqual(kwargs["timeout"], 3)
        self.assertIs(kwargs["verify"], True)
        session.return_value.close.assert_called_once()

    @override_settings(TINKOFF_TOKEN="")
    @patch("dashboard.services.client.requests.Session")
    def test_missing_token_never_sends_request(self, session):
        with (
            MarketDataClient() as client,
            self.assertRaisesMessage(MarketDataError, "not configured"),
        ):
            client.shares()
        session.return_value.post.assert_not_called()

    @patch("dashboard.services.client.requests.Session")
    def test_network_and_http_errors_do_not_expose_provider_details(self, session):
        for error in (
            requests.Timeout("test-token"),
            requests.HTTPError("secret body"),
        ):
            session.return_value.post.side_effect = error
            with (
                MarketDataClient() as client,
                self.assertRaises(MarketDataError) as caught,
            ):
                client.shares()
            self.assertEqual(str(caught.exception), "T-Invest request failed")

    @patch("dashboard.services.client.requests.Session")
    def test_invalid_json_and_response_shape(self, session):
        response = session.return_value.post.return_value
        for data in ({}, [], {"instruments": "not-a-list"}):
            response.json.return_value = data
            with MarketDataClient() as client, self.assertRaises(MarketDataError):
                client.shares()
        response.json.side_effect = ValueError("invalid json")
        with MarketDataClient() as client, self.assertRaises(MarketDataError):
            client.shares()

    @override_settings(TINKOFF_CA_BUNDLE="/trusted/custom-ca.pem")
    @patch("dashboard.services.client.requests.Session")
    def test_custom_ca_and_candle_request(self, session):
        session.return_value.post.return_value.json.return_value = {"candles": []}
        now = timezone.now()
        with MarketDataClient() as client:
            client.candles("FIGI", now - timedelta(days=180), now)
        kwargs = session.return_value.post.call_args.kwargs
        self.assertEqual(kwargs["verify"], "/trusted/custom-ca.pem")
        self.assertEqual(kwargs["json"]["interval"], "CANDLE_INTERVAL_DAY")


class GraphTests(TestCase):
    def setUp(self):
        self.share = make_share()

    @patch("dashboard.services.graph.plot", return_value="graph")
    @patch("dashboard.services.graph.MarketDataClient")
    def test_graph_keeps_precise_closes_and_180_day_window(self, factory, plot):
        client = factory.return_value.__enter__.return_value
        client.candles.return_value = [
            {
                "time": "2026-01-02T00:00:00Z",
                "close": {"units": "2", "nano": 500000000},
            },
            {
                "time": "2026-01-01T00:00:00Z",
                "close": {"units": "1", "nano": 123456789},
            },
        ]
        self.assertEqual(get_graph(self.share), "graph")
        _, start, end = client.candles.call_args.args
        self.assertEqual(end - start, timedelta(days=180))
        self.assertEqual(
            list(plot.call_args.args[0][0].y), [Decimal("1.123456789"), Decimal("2.5")]
        )

    @patch("dashboard.services.graph.MarketDataClient")
    def test_empty_and_malformed_candles(self, factory):
        client = factory.return_value.__enter__.return_value
        client.candles.return_value = []
        self.assertEqual(get_graph(self.share), "")
        client.candles.return_value = [{"time": "bad"}]
        with self.assertRaises(MarketDataError):
            get_graph(self.share)

    @patch("dashboard.services.graph.MarketDataClient")
    def test_real_plotly_renders_without_cdn(self, factory):
        factory.return_value.__enter__.return_value.candles.return_value = [
            {"time": "2026-01-01T00:00:00Z", "close": {"units": "1", "nano": 500000000}}
        ]
        graph = get_graph(self.share)
        self.assertIn("Plotly.newPlot", graph)
        self.assertNotIn('<script src="https://cdn.plot.ly', graph)

    @patch("dashboard.services.market_data.MarketDataClient")
    def test_single_quote_and_missing_quote(self, factory):
        client = factory.return_value.__enter__.return_value
        client.last_prices.return_value = [
            {
                "figi": self.share.figi,
                "price": {"units": "1", "nano": 5},
                "time": "2026-01-01T00:00:00Z",
            }
        ]
        price, timestamp = get_last_data(self.share)
        self.assertEqual(price, Decimal("1.000000005"))
        self.assertTrue(timezone.is_aware(timestamp))
        client.last_prices.return_value = []
        with self.assertRaises(MarketDataError):
            get_last_data(self.share)


@override_settings(TINKOFF_TOKEN="test-token")
class TaskTests(TestCase):
    def quote(self, share, units, nano=0, timestamp=None):
        return {
            "figi": share.figi,
            "price": {"units": str(units), "nano": nano},
            "time": (timestamp or timezone.now() + timedelta(seconds=1)).isoformat(),
        }

    @patch("dashboard.tasks.MarketDataClient")
    def test_batch_prices_directions_precision_and_timestamp(self, factory):
        shares = [
            make_share(1, last_price=10),
            make_share(2, last_price=20),
            make_share(3, last_price=30),
            make_share(4),
        ]
        timestamp = timezone.now() + timedelta(seconds=1)
        factory.return_value.__enter__.return_value.last_prices.return_value = [
            self.quote(s, price, nano, timestamp)
            for s, price, nano in zip(shares, (11, 19, 30, 1), (123456789, 0, 0, 5))
        ]
        self.assertEqual(update_last_price(), 4)
        for share in shares:
            share.refresh_from_db()
        self.assertEqual([s.is_trend_high for s in shares], [True, False, None, None])
        self.assertEqual(shares[0].last_price, Decimal("11.123456789"))
        self.assertEqual(shares[3].last_price, Decimal("1.000000005"))
        self.assertEqual(shares[0].updated_at, timestamp)
        factory.return_value.__enter__.return_value.last_prices.assert_called_once()

    @patch("dashboard.tasks.MarketDataClient")
    def test_direction_compares_against_latest_database_value(self, factory):
        share = make_share(last_price=10)

        def concurrent_update(figis):
            Share.objects.filter(pk=share.pk).update(last_price=11)
            return [self.quote(share, 10, nano=500000000)]

        factory.return_value.__enter__.return_value.last_prices.side_effect = (
            concurrent_update
        )
        self.assertEqual(update_last_price(), 1)
        share.refresh_from_db()
        self.assertEqual(share.last_price, Decimal("10.5"))
        self.assertIs(share.is_trend_high, False)

    @patch("dashboard.tasks.MarketDataClient")
    def test_stale_quote_cannot_overwrite_newer_record(self, factory):
        share = make_share(last_price=50)
        factory.return_value.__enter__.return_value.last_prices.return_value = [
            self.quote(share, 1, timestamp=timezone.now() - timedelta(days=1))
        ]
        self.assertEqual(update_last_price(), 0)
        share.refresh_from_db()
        self.assertEqual(share.last_price, Decimal("50"))

    @patch("dashboard.tasks.MarketDataClient")
    def test_invalid_and_missing_quotes_do_not_abort_remaining_shares(self, factory):
        first, second, third = make_share(1), make_share(2), make_share(3)
        bad = self.quote(first, 1)
        bad["price"] = {"units": "not-a-number"}
        factory.return_value.__enter__.return_value.last_prices.return_value = [
            bad,
            self.quote(third, 3),
        ]
        with self.assertLogs("main", level="WARNING"):
            self.assertEqual(update_last_price(), 1)
        first.refresh_from_db()
        third.refresh_from_db()
        self.assertIsNone(first.last_price)
        self.assertEqual(third.last_price, Decimal("3"))

    @patch("dashboard.tasks.MarketDataClient")
    def test_failed_batch_does_not_abort_next_batch(self, factory):
        shares = [make_share(n) for n in range(1, 102)]
        client = factory.return_value.__enter__.return_value
        client.last_prices.side_effect = [
            MarketDataError("timeout"),
            [self.quote(shares[-1], 2)],
        ]
        with self.assertLogs("main", level="WARNING"):
            self.assertEqual(update_last_price(), 1)
        self.assertEqual(client.last_prices.call_count, 2)

    @override_settings(TINKOFF_TOKEN="")
    @patch("dashboard.tasks.MarketDataClient")
    def test_no_token_skips_network(self, factory):
        with self.assertLogs("main", level="WARNING"):
            self.assertEqual(update_last_price(), 0)
        factory.assert_not_called()


class ImportTests(TestCase):
    instrument = {
        "figi": "IMPORTED",
        "isin": "ISIN",
        "name": "Original",
        "ticker": "IMPORTED",
        "currency": "rub",
        "uid": "imported-uid",
    }

    @patch("dashboard.management.commands.add_shares.MarketDataClient")
    def test_idempotent_import_updates_attributes_but_keeps_price(self, factory):
        client = factory.return_value.__enter__.return_value
        client.shares.return_value = [dict(self.instrument)]
        call_command("add_shares", stdout=StringIO())
        Share.objects.update(last_price=Decimal("123.456789123"))
        client.shares.return_value = [{**self.instrument, "name": "Renamed"}]
        call_command("add_shares", stdout=StringIO())
        call_command("add_shares", stdout=StringIO())
        self.assertEqual(Share.objects.count(), 1)
        share = Share.objects.get()
        self.assertEqual(share.name, "Renamed")
        self.assertEqual(share.last_price, Decimal("123.456789123"))

    @override_settings(TINKOFF_TOKEN="")
    def test_missing_token_is_command_error(self):
        with self.assertRaisesMessage(CommandError, "not configured"):
            call_command("add_shares", stdout=StringIO())

    @patch("dashboard.management.commands.add_shares.MarketDataClient")
    def test_invalid_instrument_is_command_error(self, factory):
        factory.return_value.__enter__.return_value.shares.return_value = [
            {"figi": "BROKEN"}
        ]
        with self.assertRaises(CommandError):
            call_command("add_shares", stdout=StringIO())
