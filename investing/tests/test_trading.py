import uuid
from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError

from investing.models import Position, Trade
from investing.services.trading import (
    TradeConflict,
    create_portfolio,
    execute_trade,
    portfolio_summary,
)

from .helpers import InvestingCase


class TradingTests(InvestingCase):
    def test_weighted_average_partial_sale_and_valuation(self):
        self.trade(quantity=2, price=100)
        self.trade(quantity=2, price=200)
        self.quote(180)
        self.trade(side="sell", quantity=1, price=200)
        self.portfolio.refresh_from_db()
        position = Position.objects.get(portfolio=self.portfolio)
        self.assertEqual(
            (position.quantity, position.cost_basis, position.average_price),
            (3, Decimal(450), Decimal(150)),
        )
        result = portfolio_summary(self.portfolio)
        self.assertEqual(result["cash"], Decimal(600))
        self.assertEqual(result["total_value"], Decimal(1140))
        self.assertEqual(result["realized_pnl"], Decimal(50))
        self.assertEqual(result["unrealized_pnl"], Decimal(90))
        self.assertEqual(result["total_pnl"], Decimal(140))
        self.assertEqual(result["return_percent"], Decimal(14))

    def test_fractional_cost_rounding_and_full_close_conserve_cash(self):
        self.trade(quantity=1, price="0.1")
        self.trade(quantity=2, price="0.2")
        position = Position.objects.get(portfolio=self.portfolio)
        self.assertEqual(position.average_price, Decimal("0.166666667"))
        self.trade(side="sell", quantity=1, price="0.3")
        self.trade(side="sell", quantity=2, price="0.3")
        position.refresh_from_db()
        self.portfolio.refresh_from_db()
        self.assertEqual((position.quantity, position.cost_basis), (0, Decimal(0)))
        self.assertEqual(self.portfolio.cash, Decimal("1000.4"))
        self.assertEqual(
            portfolio_summary(self.portfolio)["realized_pnl"], Decimal("0.4")
        )

    def test_overspending_and_overselling_have_no_effects(self):
        for side, quantity in (("buy", 11), ("sell", 1)):
            with self.assertRaises(ValidationError):
                self.trade(side=side, quantity=quantity)
        self.portfolio.refresh_from_db()
        self.assertEqual(self.portfolio.cash, Decimal(1000))
        self.assertFalse(Position.objects.exists())
        self.assertFalse(Trade.objects.exists())

    def test_trade_retry_and_conflicting_request_id(self):
        key = uuid.uuid4()
        first, created = self.trade(quantity=2, request_id=key)
        second, created_again = self.trade(quantity=2, request_id=key)
        self.assertTrue(created)
        self.assertFalse(created_again)
        self.assertEqual(first.pk, second.pk)
        for changes in ({"quantity": 3}, {"side": "sell"}, {"price": 99}):
            with self.assertRaises(TradeConflict):
                self.trade(
                    quantity=changes.pop("quantity", 2), request_id=key, **changes
                )
        self.portfolio.refresh_from_db()
        self.assertEqual(self.portfolio.cash, Decimal(800))
        self.assertEqual(Trade.objects.count(), 1)

    def test_invalid_values_are_rejected_without_writes(self):
        for quantity in (0, -1, 1.5, True, 2147483648):
            with self.subTest(quantity=quantity), self.assertRaises(ValidationError):
                self.trade(quantity=quantity)
        for price in (0, -1, "NaN", "Infinity", "1000000000000000"):
            with self.subTest(price=price), self.assertRaises(ValidationError):
                self.trade(price=price)
        self.assertFalse(Trade.objects.exists())

    def test_currency_mismatch_and_foreign_portfolio_are_rejected(self):
        self.share.currency = "usd"
        self.share.save()
        with self.assertRaises(ValidationError):
            self.trade()
        with self.assertRaises(PermissionDenied):
            execute_trade(
                self.other,
                self.portfolio.pk,
                self.share.pk,
                "buy",
                1,
                uuid.uuid4(),
                price=1,
            )
        self.assertFalse(Trade.objects.exists())

    def test_missing_quote_is_unknown_and_not_zero(self):
        self.trade(quantity=1)
        self.portfolio.refresh_from_db()
        result = portfolio_summary(self.portfolio)
        self.assertFalse(result["complete"])
        self.assertIsNone(result["total_value"])
        self.assertIsNone(result["unrealized_pnl"])
        self.assertEqual(result["cash"], Decimal(900))
        with self.assertRaises(ValidationError):
            self.trade(price=None)

    def test_default_quote_price_and_zero_capital(self):
        self.quote("12.123456789")
        trade, _ = self.trade(price=None)
        self.assertEqual(trade.price, Decimal("12.123456789"))
        empty = create_portfolio(
            self.owner, name="Empty", currency="RUB", initial_cash=0
        )
        self.assertIsNone(portfolio_summary(empty)["return_percent"])
        self.assertEqual(empty.currency, "rub")
        with self.assertRaises(ValidationError):
            create_portfolio(
                self.owner, name="Invalid", currency="rub", initial_cash=-1
            )

    def test_removed_share_is_a_validation_error(self):
        identifier = self.share.pk
        self.share.delete()
        with self.assertRaisesMessage(ValidationError, "больше не доступна"):
            execute_trade(
                self.owner,
                self.portfolio.pk,
                identifier,
                "buy",
                1,
                uuid.uuid4(),
                price=1,
            )
        self.assertFalse(Trade.objects.exists())
