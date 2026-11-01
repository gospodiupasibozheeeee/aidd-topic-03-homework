"""Additional end-to-end checks called by verify_runtime.py --features."""

import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

import requests


def verify_features(session, base, post, check, refresh, market):
    def get(path):
        response = session.get(base + path, timeout=10)
        if response.status_code != 200:
            raise AssertionError(f"GET {path}: {response.status_code}")
        return response.json()

    def wait_for(path, predicate):
        for attempt in range(150):
            result = get(path)
            if predicate(result):
                return result
            time.sleep(0.1)
        raise AssertionError(f"Background effects missing: {path}")

    share = get("/api/v1/shares/")["results"][0]
    share_id = share["id"]
    watchlist = post("/api/v1/watchlists/", payload={"name": "Feature watchlist"})
    check(watchlist.status_code == 201, "Create personal watchlist")
    watchlist_id = watchlist.json()["id"]
    item = post(
        "/api/v1/watch-items/",
        payload={
            "watchlist": watchlist_id,
            "share": share_id,
            "target": "123",
            "direction": "gte",
        },
    )
    check(item.status_code == 201, "Configure price target")
    item_id = item.json()["id"]
    portfolio = post(
        "/api/v1/portfolios/",
        payload={
            "name": "Feature portfolio",
            "currency": "rub",
            "initial_cash": "1000",
        },
    )
    check(portfolio.status_code == 201, "Create funded virtual portfolio")
    portfolio_id = portfolio.json()["id"]
    strategy = post(
        "/api/v1/strategies/",
        payload={
            "name": "Feature cycle",
            "portfolio": portfolio_id,
            "share": share_id,
            "quantity": 1,
            "buy_below": "124",
            "sell_above": "130",
            "active": True,
        },
    )
    check(strategy.status_code == 201, "Configure virtual strategy")
    strategy_id = strategy.json()["id"]
    refresh()
    notifications = wait_for("/api/v1/notifications/", lambda data: data["count"] == 1)
    check(
        notifications["results"][0]["price"] == "123.456789123",
        "Automatic threshold notification",
    )
    trades_path = f"/api/v1/portfolios/{portfolio_id}/trades/"
    trades = wait_for(trades_path, lambda data: data["count"] == 1)
    check(trades["results"][0]["automated"], "Automatic strategy purchase")
    refresh()
    check(
        get("/api/v1/notifications/")["count"] == 1 and get(trades_path)["count"] == 1,
        "Repeated current price creates no duplicate alert or strategy trade",
    )
    history = get(f"/api/v1/shares/{share_id}/history/")
    check(
        history["count"] >= 1 and bool(history["daily"]), "Persistent price history API"
    )
    history_page = session.get(base + f"/shares/{share_id}/history/", timeout=15)
    check(
        history_page.status_code == 200 and "Plotly.newPlot" in history_page.text,
        "Local history graph over HTTP",
    )

    data = {
        "share": share_id,
        "side": "buy",
        "quantity": 2,
        "price": "100",
        "request_id": str(uuid.uuid4()),
    }
    cookie_jar = session.cookies.copy()
    csrf = session.cookies["csrftoken"]

    def concurrent_post(_):
        with requests.Session() as client:
            client.cookies.update(cookie_jar)
            response = client.post(
                base + trades_path, json=data, headers={"X-CSRFToken": csrf}, timeout=20
            )
            return response.status_code, response.json()

    with ThreadPoolExecutor(max_workers=2) as pool:
        replies = list(pool.map(concurrent_post, range(2)))
    check(
        sorted(code for code, _ in replies) == [200, 201]
        and replies[0][1]["id"] == replies[1][1]["id"],
        "Concurrent HTTP retry produces one debit",
    )
    sale = post(
        trades_path,
        payload={
            "share": share_id,
            "side": "sell",
            "quantity": 1,
            "price": "120",
            "request_id": str(uuid.uuid4()),
        },
    )
    check(sale.status_code == 201, "Manual virtual sale")
    portfolio = get(f"/api/v1/portfolios/{portfolio_id}/")
    check(
        Decimal(portfolio["cash"]) == Decimal("796.543210877")
        and portfolio["summary"]["holdings"][0]["quantity"] == 2,
        "Portfolio cash and holdings after mixed trades",
    )
    failed = post(
        trades_path,
        payload={
            "share": share_id,
            "side": "sell",
            "quantity": 1000,
            "price": "120",
            "request_id": str(uuid.uuid4()),
        },
    )
    check(
        failed.status_code == 400 and get(trades_path)["count"] == 3,
        "Overselling rejected without a journal entry",
    )
    market.quotation = {"units": "135", "nano": 0}
    refresh()
    wait_for(trades_path, lambda data: data["count"] == 4)
    strategy = get(f"/api/v1/strategies/{strategy_id}/")
    check(
        strategy["next_action"] == "buy"
        and Decimal(strategy["summary"]["profit"]) == Decimal("11.543210877"),
        "Strategy completes profitable buy/sell cycle",
    )
    response = session.patch(
        base + f"/api/v1/watch-items/{item_id}/",
        json={"target": "130"},
        headers={"X-CSRFToken": session.cookies["csrftoken"]},
        timeout=5,
    )
    check(response.status_code == 200, "Reconfigure threshold")
    refresh()
    notifications = wait_for("/api/v1/notifications/", lambda data: data["count"] == 2)
    notification_id = notifications["results"][0]["id"]
    check(
        post(f"/api/v1/notifications/{notification_id}/read/").status_code == 200,
        "Mark notification read",
    )

    with requests.Session() as other:
        other.get(base + "/user/registration/", timeout=5)
        response = other.post(
            base + "/user/registration/",
            data={
                "email": "other-feature@example.com",
                "password1": "Other-feature-pass-941!",
                "password2": "Other-feature-pass-941!",
            },
            headers={"X-CSRFToken": other.cookies["csrftoken"]},
            allow_redirects=False,
            timeout=5,
        )
        check(
            response.status_code == 302
            and other.get(
                base + f"/api/v1/portfolios/{portfolio_id}/", timeout=5
            ).status_code
            == 404
            and other.get(base + "/api/v1/watchlists/", timeout=5).json()["count"] == 0,
            "Second user cannot access private portfolio or watchlists",
        )

    for path in (
        "/workspace/",
        f"/watchlists/{watchlist_id}/",
        "/notifications/",
        f"/portfolios/{portfolio_id}/",
        f"/strategies/{strategy_id}/edit/",
    ):
        check(
            session.get(base + path, timeout=10).status_code == 200,
            f"Personal HTML page {path}",
        )
    deletion = session.delete(
        base + f"/api/v1/shares/{share_id}/",
        headers={"X-CSRFToken": session.cookies["csrftoken"]},
        timeout=5,
    )
    check(deletion.status_code == 409, "Financial journal protects referenced share")
    deletion = session.delete(
        base + f"/api/v1/strategies/{strategy_id}/",
        headers={"X-CSRFToken": session.cookies["csrftoken"]},
        timeout=5,
    )
    check(
        deletion.status_code == 204 and get(trades_path)["count"] == 4,
        "Deleting strategy preserves executed trades",
    )

    check(
        get(f"/api/v1/portfolios/{portfolio_id}/strategy-runs/")["count"] == 2,
        "Deleted strategy execution journal remains available through portfolio API",
    )
