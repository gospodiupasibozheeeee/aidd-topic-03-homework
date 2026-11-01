from decimal import Decimal

from django.core.exceptions import ValidationError

from investing.models import Portfolio, Position, StrategyRun, Trade
from investing.services.strategies import save_strategy, strategy_summary

from .helpers import InvestingCase


class StrategyTests(InvestingCase):
    def test_buy_sell_cycle_profit_and_duplicate_quote(self):
        strategy = self.strategy()
        self.quote(101)
        self.assertFalse(Trade.objects.exists())
        self.quote(100, 1)
        self.quote(100, 1)
        self.quote(99, 2)
        self.assertEqual(Trade.objects.count(), 1)
        strategy.refresh_from_db()
        self.assertEqual(strategy.next_action, "sell")
        self.quote(120, 3)
        self.quote(120, 3)
        self.assertEqual(Trade.objects.count(), 2)
        self.portfolio.refresh_from_db()
        strategy.refresh_from_db()
        self.assertEqual(self.portfolio.cash, Decimal(1040))
        self.assertEqual((strategy.next_action, strategy.cycle_quantity), ("buy", 0))
        self.assertEqual(strategy_summary(strategy)["profit"], Decimal(40))
        self.assertEqual(StrategyRun.objects.count(), 2)

    def test_failed_execution_is_logged_and_can_retry_on_next_quote(self):
        Portfolio.objects.filter(pk=self.portfolio.pk).update(cash=10)
        strategy = self.strategy()
        self.quote(100)
        self.quote(100)
        self.assertFalse(Trade.objects.exists())
        self.assertEqual(StrategyRun.objects.count(), 1)
        self.assertEqual(StrategyRun.objects.get().status, "rejected")
        self.assertIn("Недостаточно", StrategyRun.objects.get().reason)
        strategy.refresh_from_db()
        self.assertEqual(strategy.next_action, "buy")
        self.quote(4, 1)
        self.assertEqual(Trade.objects.count(), 1)

    def test_pause_resume_and_late_rule_on_existing_quote(self):
        self.quote(100)
        strategy = self.strategy(active=False)
        self.quote(100)
        self.assertFalse(Trade.objects.exists())
        strategy.active = True
        strategy.save(update_fields=["active"])
        self.quote(100)
        self.assertEqual(Trade.objects.count(), 1)
        strategy.active = False
        strategy.save(update_fields=["active"])
        self.quote(120, 1)
        self.assertEqual(Trade.objects.count(), 1)

    def test_configuration_edit_preserves_quantity_of_started_cycle(self):
        strategy = self.strategy()
        self.quote(100)
        save_strategy(
            self.owner,
            strategy_id=strategy.pk,
            portfolio=self.portfolio,
            share=self.share,
            name="Renamed",
            quantity=3,
            buy_below=Decimal(100),
            sell_above=Decimal(120),
        )
        self.quote(120, 1)
        self.assertEqual(Trade.objects.filter(side="sell").get().quantity, 2)
        self.quote(100, 2)
        self.assertEqual(Trade.objects.first().quantity, 3)

    def test_manual_sale_can_cause_rejected_strategy_sale_without_negative_holdings(
        self,
    ):
        self.strategy()
        self.quote(100)
        self.trade(side="sell", quantity=2, price=110)
        self.quote(120, 1)
        self.assertEqual(StrategyRun.objects.first().status, "rejected")
        self.assertEqual(Position.objects.get().quantity, 0)

    def test_deleting_strategy_keeps_transactions_and_execution_journal(self):
        strategy = self.strategy()
        self.quote(100)
        strategy.delete()
        self.assertEqual(Trade.objects.count(), 1)
        self.assertEqual(StrategyRun.objects.count(), 1)
        self.assertIsNone(Trade.objects.get().strategy_id)
        self.assertIsNone(StrategyRun.objects.get().strategy_id)
        self.assertEqual(StrategyRun.objects.get().strategy_name, "Cycle")

    def test_thresholds_and_currency_are_validated(self):
        for data in (
            {"buy_below": Decimal(120)},
            {"quantity": 0},
            {"sell_above": Decimal(-1)},
        ):
            with self.assertRaises(ValidationError):
                self.strategy(**data)
        self.share.currency = "usd"
        self.share.save()
        with self.assertRaises(ValidationError):
            self.strategy()
