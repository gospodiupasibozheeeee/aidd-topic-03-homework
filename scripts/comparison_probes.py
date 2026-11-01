"""Independent Task 5 scenarios; executed inside each exported Django snapshot.

These adapters exercise the implementations as delivered. They never patch the
other branches and never call a real market endpoint.
"""

import json
import os
import threading
import uuid
from datetime import timedelta
from decimal import Decimal
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import Client, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from dashboard.models import Share

BRANCH = os.environ["COMPARISON_BRANCH"]
RESULTS = {}
SERIAL = 0


def share(price=Decimal(100), currency="rub", name="Proof share"):
    global SERIAL
    SERIAL += 1
    return Share.objects.create(
        figi=f"PROOF-{SERIAL}",
        isin=f"ISIN-{SERIAL}",
        name=name,
        ticker=f"P{SERIAL}",
        currency=currency,
        uid=f"proof-uid-{SERIAL}",
        last_price=price,
    )


def user():
    return get_user_model().objects.create_user(
        username=f"proof-{uuid.uuid4().hex}@example.com"
    )


def portfolio(owner, currency="rub", amount=1000):
    if BRANCH == "codex":
        from investing.services.trading import create_portfolio

        return create_portfolio(
            owner, name="Proof", currency=currency, initial_cash=amount
        )
    if BRANCH == "antigravity":
        from dashboard.models import Portfolio

        return Portfolio.objects.create(
            user=owner,
            name="Proof",
            currency=currency,
            balance=amount,
            initial_balance=amount,
        )
    from investments.models import Portfolio

    return Portfolio.objects.create(user=owner, name="Proof")


def buy(owner, pf, instrument, price=100):
    if BRANCH == "codex":
        from investing.services.trading import execute_trade

        execute_trade(
            owner, pf.pk, instrument.pk, "buy", 1, uuid.uuid4(), price=Decimal(price)
        )
    elif BRANCH == "antigravity":
        from dashboard.services.portfolio_service import buy_share

        tx, error = buy_share(pf, instrument, 1, price=Decimal(price))
        if error:
            raise ValidationError(error)
    else:
        from investments.models import Transaction
        from investments.services.portfolio import validate_transaction

        validate_transaction(pf, instrument, Transaction.Side.BUY, Decimal(1))
        Transaction.objects.create(
            portfolio=pf,
            share=instrument,
            side=Transaction.Side.BUY,
            quantity=Decimal(1),
            price=Decimal(price),
        )


def transactions(pf):
    return pf.trades if BRANCH == "codex" else pf.transactions


def probe(name, operation):
    try:
        RESULTS[name] = operation()
    except Exception as exc:
        RESULTS[name] = {"probe_error": type(exc).__name__, "message": str(exc)[:500]}


def notification_events():
    owner, instrument = user(), share(price=None)
    timestamp = timezone.now()
    if BRANCH == "codex":
        from investing.models import Notification, Watchlist
        from investing.services.monitoring import save_watch_item
        from investing.services.prices import record_quote

        watchlist = Watchlist.objects.create(owner=owner, name="Proof")
        save_watch_item(
            owner, watchlist=watchlist, share=instrument, target=Decimal(100)
        )
        send = lambda price, at: record_quote(instrument.pk, price, at)
        rows = lambda: Notification.objects.filter(owner=owner)
    elif BRANCH == "antigravity":
        from dashboard.models import PriceNotification, WatchlistItem
        from dashboard.services.monitoring_service import check_watchlist_alerts

        WatchlistItem.objects.create(user=owner, share=instrument, target_price=100)

        def send(price, at):
            instrument.last_price = price
            check_watchlist_alerts([instrument])

        rows = lambda: PriceNotification.objects.filter(user=owner)
    else:
        from investments.models import Notification, Watchlist, WatchlistItem
        from investments.services.watchlist import evaluate_item

        watchlist = Watchlist.objects.create(user=owner, name="Proof")
        item = WatchlistItem.objects.create(
            watchlist=watchlist, share=instrument, target_price=100
        )
        send = lambda price, at: evaluate_item(item, price, at)
        rows = lambda: Notification.objects.filter(user=owner)
    send(Decimal(100), timestamp)
    send(Decimal(100), timestamp)
    repeated = rows().count()
    send(Decimal(90), timestamp + timedelta(seconds=1))
    send(Decimal(100), timestamp + timedelta(seconds=2))
    return {"same_event_twice": repeated, "after_recrossing": rows().count()}


def precision():
    instrument = share(price=Decimal("100.123456789"))
    instrument.refresh_from_db()
    return {"input": "100.123456789", "stored": str(instrument.last_price)}


def search():
    instrument = share(name="Apple independent proof")
    client = Client(raise_request_exception=False)
    good = client.get("/api/v1/shares/", {"search": "^Apple independent"})
    invalid = client.get("/api/v1/shares/", {"search": "["})
    return {
        "regex_status": good.status_code,
        "regex_count": good.json().get("count") if good.status_code == 200 else None,
        "invalid_regex_status": invalid.status_code,
    }


def malformed_quantity():
    owner = user()
    pf, instrument = portfolio(owner), share()
    client = APIClient(raise_request_exception=False)
    client.force_authenticate(owner)
    if BRANCH == "codex":
        path = f"/api/v1/portfolios/{pf.pk}/trades/"
        payload = {
            "share": instrument.pk,
            "side": "buy",
            "quantity": "not-an-integer",
            "price": "100",
            "request_id": str(uuid.uuid4()),
        }
    elif BRANCH == "antigravity":
        path = "/api/v1/portfolio/buy/"
        payload = {"share_id": instrument.pk, "quantity": "not-an-integer"}
    else:
        path = "/api/v1/portfolios/buy/"
        payload = {"share_id": instrument.pk, "quantity": "not-an-integer"}
    response = client.post(path, payload, format="json")
    return {
        "path": path,
        "status": response.status_code,
        "api_available": BRANCH != "deepseek",
    }


def currency():
    owner = user()
    pf, instrument = portfolio(owner, currency="usd"), share(currency="rub")
    try:
        buy(owner, pf, instrument)
        rejected = False
    except ValidationError:
        rejected = True
    pf.refresh_from_db()
    cash = getattr(pf, "cash", getattr(pf, "balance", None))
    return {
        "accepted": not rejected,
        "wallet_currency": getattr(pf, "currency", None),
        "instrument_currency": "rub",
        "trades": transactions(pf).count(),
        "cash_after": str(cash) if cash is not None else None,
    }


def missing_quote():
    owner = user()
    pf, instrument = portfolio(owner), share()
    buy(owner, pf, instrument)
    Share.objects.filter(pk=instrument.pk).update(last_price=None)
    pf.refresh_from_db()
    if BRANCH == "codex":
        from investing.services.trading import portfolio_summary

        summary = portfolio_summary(pf)
        return {
            "market_value": summary["market_value"],
            "unrealized_pnl": summary["unrealized_pnl"],
        }
    if BRANCH == "antigravity":
        position = pf.positions.select_related("share").get()
        return {
            "market_value": position.current_value,
            "unrealized_pnl": position.unrealized_pnl,
        }
    from investments.services.portfolio import portfolio_summary

    summary = portfolio_summary(pf)
    return {
        "market_value": summary.market_value,
        "unrealized_pnl": summary.unrealized_pnl,
    }


def deletion():
    owner = user()
    pf, instrument = portfolio(owner), share()
    buy(owner, pf, instrument)
    client = APIClient(raise_request_exception=False)
    client.force_authenticate(owner)
    before = transactions(pf).count()
    response = client.delete(f"/api/v1/shares/{instrument.pk}/")
    return {
        "status": response.status_code,
        "journal_before": before,
        "journal_after": transactions(pf).count(),
    }


def foreign_portfolio():
    owner, outsider = user(), user()
    pf = portfolio(owner)
    if BRANCH == "deepseek":
        client = Client(raise_request_exception=False)
        client.force_login(owner)
        path = reverse("investments:portfolio-detail", args=[pf.pk])
    else:
        client = APIClient(raise_request_exception=False)
        client.force_authenticate(owner)
        prefix = "portfolio" if BRANCH == "antigravity" else "portfolios"
        path = f"/api/v1/{prefix}/{pf.pk}/"
    owner_status = client.get(path).status_code
    if BRANCH == "deepseek":
        client.force_login(outsider)
    else:
        client.force_authenticate(outsider)
    return {
        "owner_status": owner_status,
        "status": client.get(path).status_code,
        "interface": "html" if BRANCH == "deepseek" else "api",
    }


def history():
    instrument = share(price=None)
    timestamp = timezone.now()
    if BRANCH == "codex":
        from investing.models import PricePoint
        from investing.services.prices import record_quote

        save = lambda price, at: record_quote(instrument.pk, Decimal(price), at)
        rows = lambda: PricePoint.objects.filter(share=instrument)
    elif BRANCH == "antigravity":
        from dashboard.models import PriceHistory
        from dashboard.services.history_service import record_price

        save = lambda price, at: record_price(
            instrument, Decimal(price), recorded_at=at
        )
        rows = lambda: PriceHistory.objects.filter(share=instrument)
    else:
        from investments.models import PriceSnapshot
        from investments.services.history import record_snapshot

        save = lambda price, at: record_snapshot(
            instrument, Decimal(price), captured_at=at
        )
        rows = lambda: PriceSnapshot.objects.filter(share=instrument)
    save(100, timestamp)
    save(100, timestamp + timedelta(seconds=1))
    distinct = rows().count()
    save(101, timestamp)
    return {
        "equal_prices_distinct_timestamps": distinct,
        "rows_after_conflicting_same_timestamp": rows().count(),
    }


def strategy_retry():
    owner, instrument = user(), share(price=None)
    timestamp = timezone.now()
    if BRANCH == "codex":
        from investing.services.prices import record_quote
        from investing.services.strategies import save_strategy

        pf = portfolio(owner)
        rule = save_strategy(
            owner,
            portfolio=pf,
            share=instrument,
            name="Proof",
            quantity=1,
            buy_below=Decimal(100),
            sell_above=Decimal(120),
        )
        record_quote(instrument.pk, Decimal(100), timestamp)
        record_quote(instrument.pk, Decimal(100), timestamp)
        pf.refresh_from_db()
        return {
            "mode": "same quote twice",
            "trades": pf.trades.count(),
            "cash": str(pf.cash),
            "quantity": pf.positions.get().quantity,
        }
    if BRANCH == "antigravity":
        from dashboard.models import TradingStrategy
        from dashboard.services.strategy_service import execute_strategy

        pf = portfolio(owner)
        rule = TradingStrategy.objects.create(
            user=owner,
            portfolio=pf,
            share=instrument,
            name="Proof",
            strategy_type="THRESHOLD_BUY_SELL",
            buy_threshold=100,
            sell_threshold=120,
            trade_quantity=1,
            is_active=True,
        )
        execute_strategy(rule, Decimal(100))
        execute_strategy(rule, Decimal(100))
        pf.refresh_from_db()
        return {
            "mode": "same signal twice",
            "trades": pf.transactions.count(),
            "cash": str(pf.balance),
            "quantity": pf.positions.get().quantity,
        }
    from investments.models import Strategy
    from investments.services.strategy import evaluate_strategy

    rule = Strategy.objects.create(
        user=owner,
        share=instrument,
        name="Proof",
        buy_below=100,
        sell_above=120,
        quantity=1,
        initial_cash=1000,
        cash=1000,
    )
    first, second = Strategy.objects.get(pk=rule.pk), Strategy.objects.get(pk=rule.pk)
    evaluate_strategy(first, Decimal(100), timestamp)
    evaluate_strategy(second, Decimal(100), timestamp)
    rule.refresh_from_db()
    return {
        "mode": "two stale ORM instances (concurrency emulation)",
        "trades": rule.trades.count(),
        "cash": str(rule.cash),
        "quantity": str(rule.position_quantity),
        "quantity_in_journal": str(
            sum((tx.quantity for tx in rule.trades.all()), Decimal(0))
        ),
    }


def market_contract():
    if BRANCH == "deepseek":
        from dashboard.services.tinkoff import MarketDataError, _load_client_class

        try:
            _load_client_class()
            return {"sdk_available": True, "http_calls": []}
        except MarketDataError:
            return {"sdk_available": False, "http_calls": []}
    seen = []

    class Fixture(BaseHTTPRequestHandler):
        def do_POST(self):
            seen.append(self.path)
            if (
                self.path
                != "/rest/tinkoff.public.invest.api.contract.v1.InstrumentsService/Shares"
            ):
                self.send_error(404)
                return
            body = json.dumps({"instruments": [{"figi": "CONTRACT-PROOF"}]}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Fixture)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        with override_settings(
            TINKOFF_TOKEN="synthetic-comparison-token",
            TINKOFF_API_URL=f"http://127.0.0.1:{server.server_port}/rest",
        ):
            if BRANCH == "codex":
                from dashboard.services.client import MarketDataClient

                with MarketDataClient() as client:
                    items = client.shares()
            else:
                from dashboard.services.client import TinkoffClient

                client = TinkoffClient()
                try:
                    items = client.get_shares()
                finally:
                    client.session.close()
        return {"returned_instruments": len(items), "http_calls": seen}
    finally:
        server.shutdown()
        server.server_close()


for name, operation in (
    ("notification_events", notification_events),
    ("price_precision", precision),
    ("search_contract", search),
    ("malformed_quantity", malformed_quantity),
    ("currency_guard", currency),
    ("missing_quote_valuation", missing_quote),
    ("share_deletion", deletion),
    ("foreign_portfolio", foreign_portfolio),
    ("history_identity", history),
    ("strategy_retry", strategy_retry),
    ("market_contract", market_contract),
):
    probe(name, operation)
Path(os.environ["COMPARISON_PROBES_OUTPUT"]).write_text(
    json.dumps(RESULTS, default=str, ensure_ascii=False, indent=2) + "\n"
)
