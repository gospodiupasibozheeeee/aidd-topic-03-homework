"""Verify real HTTP, sessions, REST transport and optionally Redis/Celery.

Uses an isolated disposable database and an explicitly synthetic market server.
No broker accounts, real tokens, or external market requests are involved.
"""

import argparse
import json
import os
import secrets
import socket
import subprocess
import sys
import tempfile
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
INSTRUMENT = dict(
    figi="SMOKE-FIGI",
    isin="SMOKE-ISIN",
    name="Synthetic smoke fixture",
    ticker="SMOKE",
    currency="rub",
    uid="smoke-uid",
)


class MarketFixture(BaseHTTPRequestHandler):
    unavailable = False

    def do_POST(self):
        payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        if self.headers.get("Authorization") != "Bearer local-fixture-token":
            self.send_error(401)
            return
        if self.unavailable:
            self.send_error(503)
            return
        now = datetime.now(timezone.utc).isoformat()
        quotation = {"units": "123", "nano": 456789123}
        if self.path.endswith("/Shares"):
            response = {"instruments": [INSTRUMENT]}
        elif self.path.endswith("/GetLastPrices"):
            response = {
                "lastPrices": [
                    dict(figi=figi, price=quotation, time=now)
                    for figi in payload["instrumentId"]
                ]
            }
        elif self.path.endswith("/GetCandles"):
            response = {"candles": [{"time": now, "close": quotation}]}
        else:
            self.send_error(404)
            return
        body = json.dumps(response).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--postgres",
        action="store_true",
        help="Use POSTGRES_* and create/drop a disposable DB",
    )
    parser.add_argument(
        "--broker", help="Use a real Redis broker with isolated queue, worker and Beat"
    )
    args = parser.parse_args()
    env = os.environ.copy()
    env.update(
        DJANGO_DEBUG="true",
        DJANGO_SECRET_KEY=secrets.token_urlsafe(64),
        DJANGO_ALLOWED_HOSTS="127.0.0.1,localhost",
        TINKOFF_TOKEN="local-fixture-token",
        TINKOFF_CA_BUNDLE="",
        MARKET_UPDATE_INTERVAL="1",
        CELERY_TASK_DEFAULT_QUEUE="codex_smoke_" + secrets.token_hex(6),
    )
    processes = []
    checks = []
    pg_connection = None
    fixture = ThreadingHTTPServer(("127.0.0.1", 0), MarketFixture)
    threading.Thread(target=fixture.serve_forever, daemon=True).start()
    env["TINKOFF_API_URL"] = f"http://127.0.0.1:{fixture.server_port}/rest"
    try:
        with tempfile.TemporaryDirectory(prefix="investing-smoke-") as temporary:
            temp = Path(temporary)
            if args.postgres:
                import psycopg
                from psycopg import sql

                pg_connection = psycopg.connect(
                    dbname="postgres",
                    user=env.get("POSTGRES_USER", "postgres"),
                    password=env.get("POSTGRES_PASSWORD", "postgres"),
                    host=env.get("POSTGRES_HOST", "localhost"),
                    port=env.get("POSTGRES_PORT", "5432"),
                    autocommit=True,
                )
                db_name = "codex_smoke_" + secrets.token_hex(6)
                pg_connection.execute(
                    sql.SQL("CREATE DATABASE {}").format(sql.Identifier(db_name))
                )
                env.update(DJANGO_DB_ENGINE="postgresql", POSTGRES_DB=db_name)
            else:
                env.update(
                    DJANGO_DB_ENGINE="sqlite", SQLITE_PATH=str(temp / "db.sqlite3")
                )

            def command(*arguments):
                subprocess.run(
                    [sys.executable, *arguments],
                    cwd=ROOT,
                    env=env,
                    check=True,
                    stdout=subprocess.DEVNULL,
                )

            def check(condition, label):
                if not condition:
                    raise AssertionError(label)
                checks.append(label)

            with (temp / "runtime.log").open("w+") as log:

                def start(*arguments):
                    process = subprocess.Popen(
                        [sys.executable, *arguments],
                        cwd=ROOT,
                        env=env,
                        stdout=log,
                        stderr=log,
                    )
                    processes.append(process)
                    return process

                try:
                    command("manage.py", "migrate", "--noinput")
                    command("manage.py", "add_shares")
                    command("manage.py", "add_shares")
                    port = free_port()
                    base = f"http://127.0.0.1:{port}"
                    start("manage.py", "runserver", f"127.0.0.1:{port}", "--noreload")
                    session = requests.Session()
                    for attempt in range(100):
                        try:
                            response = session.get(base + "/", timeout=1)
                            if response.status_code == 200:
                                break
                        except requests.RequestException:
                            pass
                        time.sleep(0.1)
                    else:
                        raise AssertionError("HTTP server did not start")
                    check(
                        "Synthetic smoke fixture" in response.text,
                        "HTTP catalog and import",
                    )
                    data = session.get(base + "/api/v1/shares/", timeout=5).json()
                    check(data["count"] == 1, "Idempotent import")
                    share_id = data["results"][0]["id"]
                    if args.broker:
                        env["CELERY_BROKER_URL"] = args.broker
                        start(
                            "-m",
                            "celery",
                            "-A",
                            "config",
                            "worker",
                            "--pool=solo",
                            "--concurrency=1",
                            "--loglevel=INFO",
                            "--without-gossip",
                            "--without-mingle",
                            "--without-heartbeat",
                            "-n",
                            "codex-smoke@%h",
                        )
                        start(
                            "-m",
                            "celery",
                            "-A",
                            "config",
                            "beat",
                            "--loglevel=INFO",
                            "--schedule",
                            str(temp / "beat"),
                            "--pidfile",
                            str(temp / "beat.pid"),
                        )
                    else:
                        command(
                            "manage.py",
                            "shell",
                            "-c",
                            "from dashboard.tasks import update_last_price; update_last_price()",
                        )
                    for attempt in range(100):
                        data = session.get(
                            base + f"/api/v1/shares/{share_id}/", timeout=5
                        ).json()
                        if data["last_price"] == 123.456789123:
                            break
                        time.sleep(0.1)
                    check(
                        data["last_price"] == 123.456789123,
                        "Background price refresh and precision",
                    )
                    response = session.get(base + f"/{share_id}", timeout=15)
                    check(
                        response.status_code == 200
                        and "Plotly.newPlot" in response.text,
                        "REST candles and actual Plotly graph",
                    )
                    MarketFixture.unavailable = True
                    response = session.get(base + f"/{share_id}", timeout=5)
                    check(
                        response.status_code == 200
                        and "Рыночные данные временно недоступны" in response.text,
                        "Provider outage fallback",
                    )
                    MarketFixture.unavailable = False
                    check(
                        session.post(
                            base + "/api/v1/shares/", json={}, timeout=5
                        ).status_code
                        == 403,
                        "Anonymous API write denied",
                    )
                    session.get(base + "/user/registration/", timeout=5)

                    def post(path, data=None, payload=None):
                        return session.post(
                            base + path,
                            data=data,
                            json=payload,
                            timeout=5,
                            headers={"X-CSRFToken": session.cookies["csrftoken"]},
                            allow_redirects=False,
                        )

                    account = {
                        "email": "Smoke.User@example.com",
                        "password1": "Smoke-long-pass-942!",
                        "password2": "Smoke-long-pass-942!",
                    }
                    check(
                        post("/user/registration/", data=account).status_code == 302,
                        "Registration and automatic session",
                    )
                    record = {
                        **INSTRUMENT,
                        "figi": "HTTP-SHARE",
                        "ticker": "HTTP",
                        "uid": "http-uid",
                    }
                    response = post("/api/v1/shares/", payload=record)
                    check(
                        response.status_code == 201,
                        "Authenticated API create with CSRF",
                    )
                    created_id = response.json()["id"]
                    response = session.patch(
                        base + f"/api/v1/shares/{created_id}/",
                        json={"name": "Changed via HTTP"},
                        headers={"X-CSRFToken": session.cookies["csrftoken"]},
                        timeout=5,
                    )
                    check(
                        response.status_code == 200
                        and response.json()["name"] == "Changed via HTTP",
                        "API PATCH",
                    )
                    check(
                        session.get(
                            base + f"/delete/{created_id}", timeout=5
                        ).status_code
                        == 200,
                        "HTML delete confirmation",
                    )
                    check(
                        post(f"/delete/{created_id}").status_code == 302,
                        "HTML delete with CSRF",
                    )
                    check(
                        session.get(
                            base + f"/api/v1/shares/{created_id}/", timeout=5
                        ).status_code
                        == 404,
                        "Deleted record absent",
                    )
                    check(post("/user/logout/").status_code == 302, "POST logout")
                    check(
                        post("/api/v1/shares/", payload=record).status_code == 403,
                        "Session invalid after logout",
                    )
                    check(
                        post(
                            "/user/login/",
                            data={
                                "email": "SMOKE.USER@example.com",
                                "password": account["password1"],
                            },
                        ).status_code
                        == 302,
                        "Case insensitive login",
                    )
                    check(
                        session.get(base + "/admin/login/", timeout=5).status_code
                        == 200,
                        "Admin login page",
                    )
                    session.close()
                except Exception:
                    log.flush()
                    print((temp / "runtime.log").read_text(), file=sys.stderr)
                    raise
                finally:
                    for process in reversed(processes):
                        process.terminate()
                    for process in processes:
                        try:
                            process.wait(timeout=10)
                        except subprocess.TimeoutExpired:
                            process.kill()
                            process.wait()
    finally:
        fixture.shutdown()
        fixture.server_close()
        if pg_connection is not None:
            pg_connection.execute(
                sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(db_name))
            )
            pg_connection.close()
    print(
        json.dumps(
            {
                "database": "postgresql" if args.postgres else "sqlite",
                "broker": bool(args.broker),
                "market": "local synthetic fixture",
                "passed": len(checks),
                "checks": checks,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
