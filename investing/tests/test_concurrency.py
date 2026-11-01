import uuid
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Barrier

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import close_old_connections, connection
from django.test import TransactionTestCase, skipUnlessDBFeature
from django.utils import timezone

from dashboard.test_helpers import make_share
from investing.models import (
    Notification,
    Position,
    PricePoint,
    StrategyRun,
    Trade,
    Watchlist,
)
from investing.services.monitoring import save_watch_item
from investing.services.prices import record_quote
from investing.services.strategies import save_strategy
from investing.services.trading import create_portfolio, execute_trade


@skipUnlessDBFeature("has_select_for_update")
class ConcurrencyTests(TransactionTestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user("parallel@example.com")
        self.share = make_share()
        self.portfolio = create_portfolio(
            self.owner, name="Concurrent", currency="rub", initial_cash=100
        )

    def parallel(self, work):
        barrier = Barrier(2)

        def worker(index):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                return work(index)
            finally:
                connection.close()

        with ThreadPoolExecutor(max_workers=2) as pool:
            return list(pool.map(worker, (0, 1)))

    def test_competing_buys_cannot_overspend(self):
        def buy(index):
            try:
                execute_trade(
                    self.owner,
                    self.portfolio.pk,
                    self.share.pk,
                    "buy",
                    1,
                    uuid.uuid4(),
                    price=80,
                )
                return True
            except ValidationError:
                return False

        self.assertEqual(sorted(self.parallel(buy)), [False, True])
        self.portfolio.refresh_from_db()
        self.assertEqual(self.portfolio.cash, Decimal(20))
        self.assertEqual(Position.objects.get().quantity, 1)
        self.assertEqual(Trade.objects.count(), 1)

    def test_competing_sales_cannot_oversell(self):
        execute_trade(
            self.owner,
            self.portfolio.pk,
            self.share.pk,
            "buy",
            1,
            uuid.uuid4(),
            price=50,
        )

        def sell(index):
            try:
                execute_trade(
                    self.owner,
                    self.portfolio.pk,
                    self.share.pk,
                    "sell",
                    1,
                    uuid.uuid4(),
                    price=60,
                )
                return True
            except ValidationError:
                return False

        self.assertEqual(sorted(self.parallel(sell)), [False, True])
        self.assertEqual(Position.objects.get().quantity, 0)
        self.portfolio.refresh_from_db()
        self.assertEqual(self.portfolio.cash, Decimal(110))

    def test_same_request_creates_one_trade(self):
        key = uuid.uuid4()

        def buy(index):
            trade, _ = execute_trade(
                self.owner, self.portfolio.pk, self.share.pk, "buy", 1, key, price=50
            )
            return trade.pk

        ids = self.parallel(buy)
        self.assertEqual(ids[0], ids[1])
        self.assertEqual(Trade.objects.count(), 1)
        self.portfolio.refresh_from_db()
        self.assertEqual(self.portfolio.cash, Decimal(50))

    def test_duplicate_quote_creates_one_observation_alert_and_execution(self):
        watchlist = Watchlist.objects.create(owner=self.owner, name="Concurrent")
        save_watch_item(
            self.owner, watchlist=watchlist, share=self.share, target=Decimal(50)
        )
        save_strategy(
            self.owner,
            portfolio=self.portfolio,
            share=self.share,
            name="Concurrent",
            quantity=1,
            buy_below=Decimal(50),
            sell_above=Decimal(60),
        )
        timestamp = timezone.now()
        self.parallel(lambda index: record_quote(self.share.pk, Decimal(50), timestamp))
        self.assertEqual(PricePoint.objects.count(), 1)
        self.assertEqual(Notification.objects.count(), 1)
        self.assertEqual(Trade.objects.count(), 1)
        self.assertEqual(StrategyRun.objects.count(), 1)
        self.portfolio.refresh_from_db()
        self.assertEqual(self.portfolio.cash, Decimal(50))
