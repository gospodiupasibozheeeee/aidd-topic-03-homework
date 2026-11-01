from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import ValidationError

from investing.models import Notification, PricePoint, WatchItem
from investing.services.monitoring import save_watch_item
from investing.services.prices import record_quote

from .helpers import InvestingCase


class MonitoringTests(InvestingCase):
    def item(self, **kwargs):
        return save_watch_item(
            self.owner,
            watchlist=self.watchlist,
            share=self.share,
            **{"target": Decimal(100), **kwargs},
        )

    def test_one_notification_for_condition_despite_retries_and_crossings(self):
        item = self.item()
        self.quote(99)
        self.assertFalse(Notification.objects.exists())
        self.quote(100, 1)
        self.quote(100, 1)
        self.quote(110, 2)
        self.quote(90, 3)
        self.quote(110, 4)
        self.assertEqual(Notification.objects.count(), 1)
        item.refresh_from_db()
        self.assertIsNotNone(item.triggered_at)
        self.assertEqual(Notification.objects.get().owner, self.owner)

    def test_changed_rule_rearms_but_unchanged_save_does_not(self):
        item = self.item()
        self.quote(110)
        saved = self.item(item_id=item.pk)
        self.assertEqual(saved.revision, 1)
        self.quote(110, 1)
        self.assertEqual(Notification.objects.count(), 1)
        saved = self.item(item_id=item.pk, target=Decimal(120))
        self.assertEqual(saved.revision, 2)
        self.assertIsNone(saved.triggered_at)
        self.quote(120, 2)
        self.assertEqual(Notification.objects.count(), 2)

    def test_below_disabled_and_duplicate_items(self):
        item = self.item(direction="lte")
        self.quote(100)
        self.assertEqual(Notification.objects.count(), 1)
        with self.assertRaises(ValidationError):
            self.item()
        self.item(item_id=item.pk, target=None)
        self.quote(90, 1)
        self.assertEqual(Notification.objects.count(), 1)
        with self.assertRaises(ValidationError):
            self.item(item_id=item.pk, target=Decimal(0))

    def test_new_rule_checks_repeated_latest_quote(self):
        self.quote(100)
        self.item()
        self.quote(100)
        self.assertEqual(Notification.objects.count(), 1)

    def test_duplicate_payload_is_canonical_and_old_quotes_only_enter_history(self):
        self.item(target=Decimal(105))
        self.quote(100, 2)
        self.quote(999, 2)
        self.quote(110, 1)
        self.share.refresh_from_db()
        self.assertEqual(self.share.last_price, Decimal(100))
        self.assertEqual(PricePoint.objects.count(), 2)
        self.assertFalse(Notification.objects.exists())

    def test_atomic_quote_and_effects_on_failure(self):
        self.item()
        with patch(
            "investing.services.prices.evaluate_strategies",
            side_effect=RuntimeError("failure"),
        ):
            with self.assertRaises(RuntimeError):
                self.quote(100)
        self.share.refresh_from_db()
        self.assertIsNone(self.share.last_price)
        self.assertFalse(PricePoint.objects.exists())
        self.assertFalse(Notification.objects.exists())
        self.assertIsNone(WatchItem.objects.get().triggered_at)

    def test_notification_survives_list_removal(self):
        self.item()
        self.quote(100)
        self.watchlist.delete()
        item = Notification.objects.get()
        self.assertIsNone(item.item_id)
        self.assertIn(self.share.ticker, item.message)

    def test_invalid_quote_does_not_write_history(self):
        with self.assertRaises(ValidationError):
            record_quote(self.share.pk, Decimal(-1), self.time)
        with self.assertRaises(ValidationError):
            record_quote(self.share.pk, Decimal(1), self.time.replace(tzinfo=None))
        self.assertFalse(PricePoint.objects.exists())
