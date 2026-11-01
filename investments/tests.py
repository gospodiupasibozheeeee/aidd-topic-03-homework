from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from dashboard.models import Share
from investments.forms import StrategyForm, TransactionForm
from investments.models import (
    Notification,
    Portfolio,
    PriceSnapshot,
    Strategy,
    Transaction,
    Watchlist,
    WatchlistItem,
)
from investments.services.history import (
    build_chart,
    get_history,
    history_context,
    record_snapshot,
    summarize,
)
from investments.services.market_events import process_market_updates
from investments.services.portfolio import (
    PortfolioError,
    portfolio_positions,
    portfolio_summary,
    quantity_held,
)
from investments.services.strategy import (
    evaluate_strategies,
    evaluate_strategy,
    reset_strategy,
    strategy_summary,
)
from investments.services.watchlist import evaluate_item, evaluate_watchlist

User = get_user_model()


def make_user(email="investor@example.com"):
    return User.objects.create_user(
        username=email, email=email, password="StrongPass123!"
    )


def make_share(figi="BBG000B9XRY4", ticker="AAPL", name="Apple Inc.", price="100"):
    return Share.objects.create(
        figi=figi,
        isin=f"ISIN-{figi}",
        name=name,
        ticker=ticker,
        currency="RUB",
        last_price=Decimal(price),
        is_trend_high=True,
    )


class PortfolioServiceTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.share = make_share()
        self.portfolio = Portfolio.objects.create(user=self.user, name="Основной")

    def test_average_cost_and_summary(self):
        Transaction.objects.create(
            portfolio=self.portfolio,
            share=self.share,
            side=Transaction.Side.BUY,
            quantity=Decimal("10"),
            price=Decimal("80"),
        )
        Transaction.objects.create(
            portfolio=self.portfolio,
            share=self.share,
            side=Transaction.Side.BUY,
            quantity=Decimal("5"),
            price=Decimal("90"),
        )

        positions = portfolio_positions(self.portfolio)
        self.assertEqual(len(positions), 1)
        position = positions[0]
        self.assertEqual(position.quantity, Decimal("15"))
        self.assertEqual(
            position.average_price.quantize(Decimal("0.00000001")),
            Decimal("83.33333333"),
        )
        self.assertEqual(position.market_value, Decimal("1500"))
        self.assertEqual(position.unrealized_pnl, Decimal("250"))

        summary = portfolio_summary(self.portfolio)
        self.assertEqual(summary.total_cost, Decimal("1250"))
        self.assertEqual(summary.total_pnl, Decimal("250"))

    def test_sell_reduces_position_and_tracks_realized_pnl(self):
        Transaction.objects.create(
            portfolio=self.portfolio,
            share=self.share,
            side=Transaction.Side.BUY,
            quantity=Decimal("10"),
            price=Decimal("80"),
        )
        Transaction.objects.create(
            portfolio=self.portfolio,
            share=self.share,
            side=Transaction.Side.SELL,
            quantity=Decimal("4"),
            price=Decimal("100"),
        )
        position = portfolio_positions(self.portfolio)[0]
        self.assertEqual(position.quantity, Decimal("6"))
        self.assertEqual(position.realized_pnl, Decimal("80"))
        self.assertEqual(quantity_held(self.portfolio, self.share), Decimal("6"))

    def test_sell_more_than_held_raises(self):
        Transaction.objects.create(
            portfolio=self.portfolio,
            share=self.share,
            side=Transaction.Side.BUY,
            quantity=Decimal("1"),
            price=Decimal("80"),
        )
        Transaction.objects.create(
            portfolio=self.portfolio,
            share=self.share,
            side=Transaction.Side.SELL,
            quantity=Decimal("2"),
            price=Decimal("100"),
        )
        with self.assertRaises(PortfolioError):
            portfolio_positions(self.portfolio)

    def test_transaction_form_rejects_oversell(self):
        Transaction.objects.create(
            portfolio=self.portfolio,
            share=self.share,
            side=Transaction.Side.BUY,
            quantity=Decimal("1"),
            price=Decimal("80"),
        )
        form = TransactionForm(
            data={
                "share": self.share.pk,
                "side": Transaction.Side.SELL,
                "quantity": "2",
                "price": "100",
                "note": "",
            },
            portfolio=self.portfolio,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("quantity", form.errors)


class WatchlistServiceTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.share = make_share()
        self.watchlist = Watchlist.objects.create(user=self.user, name="Мой список")
        self.item = WatchlistItem.objects.create(
            watchlist=self.watchlist,
            share=self.share,
            target_price=Decimal("100"),
            direction=WatchlistItem.Direction.ABOVE,
        )

    def test_notification_created_once_and_recreated_after_recovery(self):
        self.assertFalse(evaluate_item(self.item, Decimal("99")))
        self.assertTrue(evaluate_item(self.item, Decimal("100")))
        self.assertEqual(
            Notification.objects.filter(user=self.user).count(),
            1,
        )
        self.assertFalse(evaluate_item(self.item, Decimal("101")))
        self.assertEqual(
            Notification.objects.filter(user=self.user).count(),
            1,
        )

        self.assertFalse(evaluate_item(self.item, Decimal("99")))
        self.item.refresh_from_db()
        self.assertFalse(self.item.alert_active)

        self.assertTrue(evaluate_item(self.item, Decimal("100")))
        self.assertEqual(
            Notification.objects.filter(user=self.user).count(),
            2,
        )

    def test_below_direction(self):
        self.item.direction = WatchlistItem.Direction.BELOW
        self.item.target_price = Decimal("90")
        self.item.save()
        self.assertFalse(evaluate_item(self.item, Decimal("95")))
        self.assertTrue(evaluate_item(self.item, Decimal("90")))

    def test_batch_evaluation(self):
        price = Decimal("100")
        events = evaluate_watchlist({self.share.figi: (price, timezone.now())})
        self.assertEqual(events, 1)


class HistoryServiceTests(TestCase):
    def setUp(self):
        self.share = make_share()

    def test_record_and_summarize(self):
        now = timezone.now()
        record_snapshot(self.share, Decimal("100"), now - timedelta(days=5))
        record_snapshot(self.share, Decimal("110"), now)
        snapshots = get_history(self.share, 30)
        self.assertEqual(len(snapshots), 2)
        summary = summarize(snapshots)
        self.assertEqual(summary.absolute_change, Decimal("10"))
        self.assertEqual(summary.percent_change, Decimal("10"))
        self.assertEqual(summary.minimum, Decimal("100"))
        self.assertEqual(summary.maximum, Decimal("110"))

    def test_chart_and_context(self):
        now = timezone.now()
        record_snapshot(self.share, Decimal("100"), now - timedelta(days=2))
        record_snapshot(self.share, Decimal("105"), now)
        snapshots = get_history(self.share, 7)
        chart = build_chart(self.share, snapshots)
        self.assertIn("<div", chart)
        self.assertIn("105", chart)

        context = history_context(self.share, 7)
        self.assertEqual(context["period"], 7)
        self.assertEqual(context["summary"].points, 2)

    def test_duplicate_snapshot_is_idempotent(self):
        at = timezone.now()
        first = record_snapshot(self.share, Decimal("100"), at)
        second = record_snapshot(self.share, Decimal("101"), at)
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(PriceSnapshot.objects.count(), 1)


class StrategyServiceTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.share = make_share(price="100")
        self.strategy = Strategy.objects.create(
            user=self.user,
            name="Тестовая",
            share=self.share,
            buy_below=Decimal("100"),
            sell_above=Decimal("120"),
            quantity=Decimal("10"),
            initial_cash=Decimal("10000"),
            cash=Decimal("10000"),
        )

    def test_buy_and_sell_cycle(self):
        buy = evaluate_strategy(self.strategy, Decimal("99"))
        self.assertIsNotNone(buy)
        self.strategy.refresh_from_db()
        self.assertEqual(self.strategy.position_quantity, Decimal("10"))
        self.assertEqual(self.strategy.cash, Decimal("9010"))

        self.assertIsNone(evaluate_strategy(self.strategy, Decimal("98")))
        self.assertEqual(self.strategy.trades.count(), 1)

        sell = evaluate_strategy(self.strategy, Decimal("121"))
        self.assertIsNotNone(sell)
        self.strategy.refresh_from_db()
        self.assertEqual(self.strategy.position_quantity, Decimal("0"))
        self.assertEqual(self.strategy.realized_pnl, Decimal("220.00"))
        self.assertEqual(self.strategy.trades.count(), 2)

        summary = strategy_summary(self.strategy)
        self.assertEqual(summary.profit, Decimal("220.00"))
        self.assertEqual(summary.return_percent, Decimal("2.20"))

    def test_no_buy_when_cash_is_insufficient(self):
        self.strategy.quantity = Decimal("1000")
        self.strategy.save()
        self.assertIsNone(evaluate_strategy(self.strategy, Decimal("99")))
        self.assertEqual(self.strategy.trades.count(), 0)

    def test_reset(self):
        evaluate_strategy(self.strategy, Decimal("99"))
        reset_strategy(self.strategy)
        self.strategy.refresh_from_db()
        self.assertEqual(self.strategy.cash, Decimal("10000"))
        self.assertEqual(self.strategy.position_quantity, Decimal("0"))
        self.assertEqual(self.strategy.trades.count(), 0)

    def test_batch_evaluation(self):
        events = evaluate_strategies({self.share.figi: (Decimal("99"), timezone.now())})
        self.assertEqual(events, 1)

    def test_form_rejects_invalid_thresholds(self):
        form = StrategyForm(
            data={
                "name": "Некорректная",
                "share": self.share.pk,
                "buy_below": "120",
                "sell_above": "100",
                "quantity": "1",
                "initial_cash": "1000",
                "is_active": "on",
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("sell_above", form.errors)


class MarketEventsTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.share = make_share(price="100")
        watchlist = Watchlist.objects.create(user=self.user, name="Список")
        self.item = WatchlistItem.objects.create(
            watchlist=watchlist,
            share=self.share,
            target_price=Decimal("100"),
            direction=WatchlistItem.Direction.ABOVE,
        )
        self.strategy = Strategy.objects.create(
            user=self.user,
            name="Стратегия",
            share=self.share,
            buy_below=Decimal("100"),
            sell_above=Decimal("120"),
            quantity=Decimal("1"),
            initial_cash=Decimal("1000"),
            cash=Decimal("1000"),
        )

    def test_process_market_updates_creates_all_effects(self):
        result = process_market_updates(
            {self.share.figi: (Decimal("100"), timezone.now())}
        )
        self.assertEqual(result.snapshots, 1)
        self.assertEqual(result.watchlist_events, 1)
        self.assertEqual(result.strategy_events, 1)
        self.assertEqual(PriceSnapshot.objects.count(), 1)
        self.assertEqual(Notification.objects.count(), 1)
        self.assertEqual(self.strategy.trades.count(), 1)


class InvestmentViewsTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.other = make_user("other@example.com")
        self.share = make_share()
        self.client.force_login(self.user)

    def test_portfolio_requires_authentication(self):
        self.client.logout()
        response = self.client.get(reverse("investments:portfolio-list"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/user/login/", response.url)
        self.client.force_login(self.user)

    def test_create_portfolio_and_add_transaction(self):
        response = self.client.post(
            reverse("investments:portfolio-create"), {"name": "Портфель"}
        )
        self.assertEqual(response.status_code, 302)
        portfolio = Portfolio.objects.get(name="Портфель")
        response = self.client.post(
            reverse("investments:portfolio-detail", args=[portfolio.pk]),
            {
                "share": self.share.pk,
                "side": Transaction.Side.BUY,
                "quantity": "2",
                "price": "90",
                "note": "тест",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(portfolio.transactions.count(), 1)
        self.assertEqual(quantity_held(portfolio, self.share), Decimal("2"))

    def test_portfolio_detail_renders_positions(self):
        portfolio = Portfolio.objects.create(user=self.user, name="Детали")
        Transaction.objects.create(
            portfolio=portfolio,
            share=self.share,
            side=Transaction.Side.BUY,
            quantity=Decimal("2"),
            price=Decimal("90"),
        )
        response = self.client.get(
            reverse("investments:portfolio-detail", args=[portfolio.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Позиции")
        self.assertContains(response, "AAPL")

    def test_watchlist_detail_renders_items(self):
        watchlist = Watchlist.objects.create(user=self.user, name="Детали")
        WatchlistItem.objects.create(
            watchlist=watchlist,
            share=self.share,
            target_price=Decimal("100"),
        )
        response = self.client.get(
            reverse("investments:watchlist-detail", args=[watchlist.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Инструменты")
        self.assertContains(response, "AAPL")

    def test_strategy_detail_renders_summary(self):
        strategy = Strategy.objects.create(
            user=self.user,
            name="Детали",
            share=self.share,
            buy_below=Decimal("90"),
            sell_above=Decimal("120"),
            quantity=Decimal("1"),
            initial_cash=Decimal("1000"),
            cash=Decimal("1000"),
        )
        response = self.client.get(
            reverse("investments:strategy-detail", args=[strategy.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Параметры")
        self.assertContains(response, "Журнал сделок")

    def test_other_user_cannot_open_portfolio(self):
        portfolio = Portfolio.objects.create(user=self.other, name="Чужой")
        response = self.client.get(
            reverse("investments:portfolio-detail", args=[portfolio.pk])
        )
        self.assertEqual(response.status_code, 404)

    def test_watchlist_add_item_and_notification_page(self):
        watchlist = Watchlist.objects.create(user=self.user, name="Список")
        response = self.client.post(
            reverse("investments:watchlist-detail", args=[watchlist.pk]),
            {
                "share": self.share.pk,
                "target_price": "100",
                "direction": WatchlistItem.Direction.ABOVE,
                "is_active": "on",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(watchlist.items.count(), 1)
        response = self.client.get(reverse("investments:notifications"))
        self.assertEqual(response.status_code, 200)

    def test_create_strategy_and_evaluate(self):
        response = self.client.post(
            reverse("investments:strategy-create"),
            {
                "name": "Стратегия",
                "share": self.share.pk,
                "buy_below": "100",
                "sell_above": "120",
                "quantity": "1",
                "initial_cash": "1000",
                "is_active": "on",
            },
        )
        self.assertEqual(response.status_code, 302)
        strategy = Strategy.objects.get(name="Стратегия")
        self.share.last_price = Decimal("99")
        self.share.save(update_fields=["last_price"])
        response = self.client.post(
            reverse("investments:strategy-evaluate", args=[strategy.pk])
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(strategy.trades.count(), 1)

    def test_price_history_is_public(self):
        now = timezone.now()
        record_snapshot(self.share, Decimal("100"), now - timedelta(days=1))
        record_snapshot(self.share, Decimal("105"), now)
        response = self.client.get(
            reverse("investments:price-history", args=[self.share.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "105")

    def test_strategy_form_is_rendered(self):
        response = self.client.get(reverse("investments:strategy-create"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Цена покупки")


class DashboardTaskIntegrationTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.share = make_share(price="100")

    @patch("dashboard.tasks.get_last_prices")
    def test_price_task_records_history(self, get_last_prices):
        from dashboard.tasks import update_last_price

        get_last_prices.return_value = {
            self.share.figi: (Decimal("101"), timezone.now())
        }
        update_last_price()
        self.assertEqual(PriceSnapshot.objects.filter(share=self.share).count(), 1)
