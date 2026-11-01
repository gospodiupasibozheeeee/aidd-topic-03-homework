from decimal import Decimal

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class DecimalMigrationTests(TransactionTestCase):
    before = [("dashboard", "0007_add_updated_at")]
    after = [("dashboard", "0008_decimal_prices_and_timestamp_state")]

    def test_existing_quotes_and_nulls_survive_upgrade(self):
        executor = MigrationExecutor(connection)
        executor.migrate(self.before)
        try:
            old_share = executor.loader.project_state(self.before).apps.get_model(
                "dashboard", "Share"
            )
            for number, price in ((1, 123.123456789), (2, None)):
                old_share.objects.create(
                    figi=f"LEGACY{number}",
                    isin=f"ISIN{number}",
                    name=f"Legacy {number}",
                    ticker=f"LEGACY{number}",
                    currency="rub",
                    uid=f"legacy-{number}",
                    last_price=price,
                )
            executor = MigrationExecutor(connection)
            executor.migrate(self.after)
            new_share = executor.loader.project_state(self.after).apps.get_model(
                "dashboard", "Share"
            )
            self.assertEqual(new_share.objects.count(), 2)
            self.assertEqual(
                new_share.objects.get(figi="LEGACY1").last_price,
                Decimal("123.123456789"),
            )
            self.assertIsNone(new_share.objects.get(figi="LEGACY2").last_price)
        finally:
            MigrationExecutor(connection).migrate(self.after)
