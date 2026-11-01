import uuid
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from dashboard.test_helpers import make_share
from investing.models import PricePoint, Watchlist
from investing.services.prices import record_quote
from investing.services.strategies import save_strategy
from investing.services.trading import create_portfolio, execute_trade


class InvestingCase(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user("investor@example.com")
        self.other = get_user_model().objects.create_user("other@example.com")
        self.share = make_share()
        self.portfolio = create_portfolio(
            self.owner, name="Main", currency="rub", initial_cash=1000
        )
        self.watchlist = Watchlist.objects.create(owner=self.owner, name="Main")
        self.time = timezone.now() + timedelta(hours=1)

    def quote(self, price, offset=0, share=None):
        share = share or self.share
        timestamp = self.time + timedelta(seconds=offset)
        record_quote(share.pk, Decimal(str(price)), timestamp)
        share.refresh_from_db()
        return PricePoint.objects.get(share=share, observed_at=timestamp)

    def trade(self, side="buy", quantity=1, price=100, **kwargs):
        return execute_trade(
            self.owner,
            self.portfolio.pk,
            self.share.pk,
            side,
            quantity,
            kwargs.pop("request_id", uuid.uuid4()),
            price=price,
            **kwargs,
        )

    def strategy(self, **kwargs):
        values = dict(
            portfolio=self.portfolio,
            share=self.share,
            name="Cycle",
            quantity=2,
            buy_below=Decimal(100),
            sell_above=Decimal(120),
        )
        return save_strategy(self.owner, **{**values, **kwargs})
