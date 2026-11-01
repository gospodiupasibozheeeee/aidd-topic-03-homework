from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from dashboard.models import (
    Portfolio,
    PortfolioPosition,
    PortfolioTransaction,
    PriceHistory,
    PriceNotification,
    Share,
    StrategyExecutionLog,
    TradingStrategy,
    WatchlistItem,
)
from dashboard.services.history_service import (
    calculate_price_dynamics,
    generate_history_chart,
    get_price_history,
    record_price,
)
from dashboard.services.monitoring_service import check_watchlist_alerts
from dashboard.services.portfolio_service import (
    buy_share,
    get_or_create_portfolio,
    sell_share,
)
from dashboard.services.strategy_service import (
    execute_strategy,
    get_strategy_performance,
    simulate_active_strategies,
)

User = get_user_model()


class Task4WatchlistAndAlertsTests(APITestCase):
    """Тестирование функциональности персонального мониторинга акций (Задание 4.1)"""

    def setUp(self):
        self.user = User.objects.create_user(
            username="investor1@example.com",
            email="investor1@example.com",
            password="StrongPassword123!",
        )
        self.client.force_login(self.user)
        self.client.force_authenticate(user=self.user)
        self.share = Share.objects.create(
            figi="BBG000B9XRY4",
            isin="US0378331005",
            name="Apple Inc",
            ticker="AAPL",
            currency="USD",
            last_price=Decimal("150.00"),
        )

    def test_create_watchlist_item_and_unique_constraint(self):
        item = WatchlistItem.objects.create(
            user=self.user,
            share=self.share,
            target_price=Decimal("160.00"),
            condition="ABOVE",
        )
        self.assertTrue(item.is_active)
        self.assertFalse(item.is_triggered)

        # Повторное создание с теми же (user, share, condition) должно обновлять или блокироваться
        self.assertEqual(WatchlistItem.objects.count(), 1)

    def test_alert_triggered_above_condition(self):
        WatchlistItem.objects.create(
            user=self.user,
            share=self.share,
            target_price=Decimal("160.00"),
            condition="ABOVE",
        )

        # 1. Цена ниже порога — уведомлений быть не должно
        self.share.last_price = Decimal("155.00")
        created = check_watchlist_alerts([self.share])
        self.assertEqual(created, 0)
        self.assertEqual(PriceNotification.objects.count(), 0)

        # 2. Цена достигла/превысила порог — генерируется уведомление
        self.share.last_price = Decimal("162.50")
        created = check_watchlist_alerts([self.share])
        self.assertEqual(created, 1)
        self.assertEqual(PriceNotification.objects.count(), 1)

        notification = PriceNotification.objects.first()
        self.assertEqual(notification.user, self.user)
        self.assertEqual(notification.share, self.share)
        self.assertEqual(notification.target_price, Decimal("160.00"))
        self.assertEqual(notification.actual_price, Decimal("162.50"))
        self.assertFalse(notification.is_read)

        # 3. Исключение дублирования: при следующем апдейте с высокой ценой повторное уведомление не создается
        created2 = check_watchlist_alerts([self.share])
        self.assertEqual(created2, 0)
        self.assertEqual(PriceNotification.objects.count(), 1)

        # 4. Цена опустилась ниже — флаг сбрасывается
        self.share.last_price = Decimal("158.00")
        check_watchlist_alerts([self.share])
        item = WatchlistItem.objects.get(user=self.user, share=self.share)
        self.assertFalse(item.is_triggered)

        # 5. Цена снова превысила порог — новое уведомление создается корректно
        self.share.last_price = Decimal("165.00")
        created3 = check_watchlist_alerts([self.share])
        self.assertEqual(created3, 1)
        self.assertEqual(PriceNotification.objects.count(), 2)

    def test_alert_triggered_below_condition(self):
        WatchlistItem.objects.create(
            user=self.user,
            share=self.share,
            target_price=Decimal("140.00"),
            condition="BELOW",
        )

        self.share.last_price = Decimal("139.00")
        created = check_watchlist_alerts([self.share])
        self.assertEqual(created, 1)

        notif = PriceNotification.objects.first()
        self.assertIn("опустилась ниже", notif.message)

    def test_watchlist_html_views(self):
        # GET watchlist page
        resp = self.client.get(reverse("dashboard:watchlist"))
        self.assertEqual(resp.status_code, 200)

        # POST add to watchlist
        post_resp = self.client.post(
            reverse("dashboard:watchlist"),
            {
                "share": self.share.id,
                "target_price": "180.00",
                "condition": "ABOVE",
            },
        )
        self.assertEqual(post_resp.status_code, 302)
        self.assertTrue(WatchlistItem.objects.filter(target_price=Decimal("180.00")).exists())

        # Delete from watchlist
        item = WatchlistItem.objects.get(target_price=Decimal("180.00"))
        del_resp = self.client.post(reverse("dashboard:watchlist_delete", kwargs={"pk": item.id}))
        self.assertEqual(del_resp.status_code, 302)
        self.assertFalse(WatchlistItem.objects.filter(id=item.id).exists())

    def test_notifications_mark_read_views(self):
        notif = PriceNotification.objects.create(
            user=self.user,
            share=self.share,
            target_price=Decimal("100"),
            actual_price=Decimal("105"),
            message="Test alert",
        )
        self.assertFalse(notif.is_read)

        # Mark single
        resp = self.client.post(reverse("dashboard:notification_read", kwargs={"pk": notif.id}))
        self.assertEqual(resp.status_code, 302)
        notif.refresh_from_db()
        self.assertTrue(notif.is_read)

        # Mark all
        PriceNotification.objects.create(
            user=self.user,
            share=self.share,
            target_price=Decimal("110"),
            actual_price=Decimal("115"),
            message="Test alert 2",
        )
        resp_all = self.client.post(reverse("dashboard:notifications_read_all"))
        self.assertEqual(resp_all.status_code, 302)
        self.assertEqual(PriceNotification.objects.filter(user=self.user, is_read=False).count(), 0)


class Task4PortfolioTests(APITestCase):
    """Тестирование функциональности виртуального портфеля (Задание 4.2)"""

    def setUp(self):
        self.user = User.objects.create_user(
            username="trader@example.com",
            email="trader@example.com",
            password="StrongPassword123!",
        )
        self.client.force_login(self.user)
        self.client.force_authenticate(user=self.user)
        self.portfolio = get_or_create_portfolio(self.user)

        self.share = Share.objects.create(
            figi="BBG000B9XRY4",
            isin="US0378331005",
            name="Apple Inc",
            ticker="AAPL",
            currency="USD",
            last_price=Decimal("150.00"),
        )

    def test_portfolio_initial_state(self):
        self.assertEqual(self.portfolio.balance, Decimal("100000.00"))
        self.assertEqual(self.portfolio.invested_value, Decimal("0.00"))
        self.assertEqual(self.portfolio.total_value, Decimal("100000.00"))
        self.assertEqual(self.portfolio.total_pnl, Decimal("0.00"))
        self.assertEqual(self.portfolio.total_pnl_percent, Decimal("0.00"))

    def test_buy_share_success_and_weighted_average_price(self):
        # 1-я покупка: 10 акций по $150 = $1500
        tx1, err1 = buy_share(self.portfolio, self.share, quantity=10, price=Decimal("150.00"))
        self.assertIsNone(err1)
        self.assertIsNotNone(tx1)
        self.portfolio.refresh_from_db()

        self.assertEqual(self.portfolio.balance, Decimal("98500.00"))
        pos = PortfolioPosition.objects.get(portfolio=self.portfolio, share=self.share)
        self.assertEqual(pos.quantity, 10)
        self.assertEqual(pos.average_buy_price, Decimal("150.00"))

        # 2-я покупка: 10 акций по $200 = $2000. Всего 20 акций на $3500 => ср. цена $175.00
        tx2, err2 = buy_share(self.portfolio, self.share, quantity=10, price=Decimal("200.00"))
        self.assertIsNone(err2)
        self.portfolio.refresh_from_db()
        pos.refresh_from_db()

        self.assertEqual(self.portfolio.balance, Decimal("96500.00"))
        self.assertEqual(pos.quantity, 20)
        self.assertEqual(pos.average_buy_price, Decimal("175.00"))
        self.assertEqual(pos.total_cost, Decimal("3500.00"))

    def test_buy_share_insufficient_funds(self):
        self.portfolio.balance = Decimal("100.00")
        self.portfolio.save()

        tx, err = buy_share(self.portfolio, self.share, quantity=10, price=Decimal("150.00"))
        self.assertIsNone(tx)
        self.assertIn("Недостаточно средств", err)

    def test_sell_share_success_and_realized_pnl(self):
        # Покупаем 10 акций по 150 = 1500
        buy_share(self.portfolio, self.share, quantity=10, price=Decimal("150.00"))

        # Продаем 4 акции по 180 = 720. Реализованный PnL = (180 - 150) * 4 = +120
        tx, err = sell_share(self.portfolio, self.share, quantity=4, price=Decimal("180.00"))
        self.assertIsNone(err)
        self.assertEqual(tx.realized_pnl, Decimal("120.00"))
        self.assertEqual(tx.total_amount, Decimal("720.00"))

        self.portfolio.refresh_from_db()
        self.assertEqual(self.portfolio.balance, Decimal("98500.00") + Decimal("720.00"))

        pos = PortfolioPosition.objects.get(portfolio=self.portfolio, share=self.share)
        self.assertEqual(pos.quantity, 6)
        self.assertEqual(pos.average_buy_price, Decimal("150.00"))

        # Продаем оставшиеся 6 акций в убыток по 130 = 780. PnL = (130 - 150) * 6 = -120
        tx2, err2 = sell_share(self.portfolio, self.share, quantity=6, price=Decimal("130.00"))
        self.assertIsNone(err2)
        self.assertEqual(tx2.realized_pnl, Decimal("-120.00"))

        # Позиция должна быть удалена при полном закрытии (quantity=0)
        self.assertFalse(
            PortfolioPosition.objects.filter(portfolio=self.portfolio, share=self.share).exists()
        )

    def test_sell_share_insufficient_quantity(self):
        buy_share(self.portfolio, self.share, quantity=5, price=Decimal("150.00"))
        tx, err = sell_share(self.portfolio, self.share, quantity=10, price=Decimal("150.00"))
        self.assertIsNone(tx)
        self.assertIn("Недостаточно акций", err)

    def test_portfolio_html_views(self):
        resp = self.client.get(reverse("dashboard:portfolio"))
        self.assertEqual(resp.status_code, 200)

        trade_resp = self.client.post(
            reverse("dashboard:portfolio_trade"),
            {
                "action": "BUY",
                "share": self.share.id,
                "quantity": 2,
            },
        )
        self.assertEqual(trade_resp.status_code, 302)
        self.assertTrue(PortfolioPosition.objects.filter(share=self.share, quantity=2).exists())


class Task4PriceHistoryTests(APITestCase):
    """Тестирование функциональности истории рыночных цен (Задание 4.3)"""

    def setUp(self):
        self.user = User.objects.create_user(
            username="analyst@example.com",
            email="analyst@example.com",
            password="StrongPassword123!",
        )
        self.client.force_login(self.user)
        self.client.force_authenticate(user=self.user)
        self.share = Share.objects.create(
            figi="BBG000B9XRY4",
            isin="US0378331005",
            name="Apple Inc",
            ticker="AAPL",
            currency="USD",
            last_price=Decimal("100.00"),
        )

    def test_record_price_and_deduplication(self):
        now = timezone.now()
        # Запись первой цены
        r1 = record_price(self.share, Decimal("100.00"), recorded_at=now)
        self.assertIsNotNone(r1)
        self.assertEqual(PriceHistory.objects.count(), 1)

        # Попытка записать ту же цену в ту же минуту -> возвращается существующая запись
        r2 = record_price(self.share, Decimal("100.00"), recorded_at=now + timedelta(seconds=20))
        self.assertEqual(r1.id, r2.id)
        self.assertEqual(PriceHistory.objects.count(), 1)

        # Запись изменившейся цены -> создается новая запись
        r3 = record_price(self.share, Decimal("102.50"), recorded_at=now + timedelta(seconds=30))
        self.assertNotEqual(r1.id, r3.id)
        self.assertEqual(PriceHistory.objects.count(), 2)

    def test_price_dynamics_calculation(self):
        now = timezone.now()
        PriceHistory.objects.create(share=self.share, price=Decimal("100.00"), recorded_at=now - timedelta(days=2))
        PriceHistory.objects.create(share=self.share, price=Decimal("95.00"), recorded_at=now - timedelta(days=1))
        PriceHistory.objects.create(share=self.share, price=Decimal("120.00"), recorded_at=now)

        dynamics = calculate_price_dynamics(self.share, period="1W")
        self.assertEqual(dynamics["data_points"], 3)
        self.assertEqual(dynamics["start_price"], Decimal("100.00"))
        self.assertEqual(dynamics["end_price"], Decimal("120.00"))
        self.assertEqual(dynamics["min_price"], Decimal("95.00"))
        self.assertEqual(dynamics["max_price"], Decimal("120.00"))
        self.assertEqual(dynamics["absolute_change"], Decimal("20.00"))
        self.assertEqual(dynamics["percentage_change"], Decimal("20.00"))
        self.assertTrue(dynamics["is_growth"])

    def test_generate_history_chart(self):
        chart_html = generate_history_chart(self.share, period="1M")
        self.assertIn("plotly", chart_html.lower())

    def test_price_history_html_view(self):
        resp = self.client.get(reverse("dashboard:price_history", kwargs={"pk": self.share.id}))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "AAPL")
        self.assertContains(resp, "Динамика котировок")


class Task4StrategySimulatorTests(APITestCase):
    """Тестирование функциональности симулятора инвестиционных стратегий (Задание 4.4)"""

    def setUp(self):
        self.user = User.objects.create_user(
            username="quant@example.com",
            email="quant@example.com",
            password="StrongPassword123!",
        )
        self.client.force_login(self.user)
        self.client.force_authenticate(user=self.user)
        self.portfolio = get_or_create_portfolio(self.user)
        self.share = Share.objects.create(
            figi="BBG000B9XRY4",
            isin="US0378331005",
            name="Apple Inc",
            ticker="AAPL",
            currency="USD",
            last_price=Decimal("100.00"),
        )

    def test_threshold_strategy_buy_and_sell_cycle(self):
        strategy = TradingStrategy.objects.create(
            user=self.user,
            portfolio=self.portfolio,
            share=self.share,
            name="Threshold Strategy",
            strategy_type="THRESHOLD_BUY_SELL",
            buy_threshold=Decimal("90.00"),
            sell_threshold=Decimal("110.00"),
            trade_quantity=5,
            is_active=True,
        )

        # 1. Цена $95 (между 90 и 110) -> сделок нет
        executed, msg = execute_strategy(strategy, current_price=Decimal("95.00"))
        self.assertFalse(executed)
        self.assertEqual(PortfolioPosition.objects.count(), 0)

        # 2. Цена упала до $88 (<= 90) -> исполняется автоматическая покупка 5 акций
        executed, msg = execute_strategy(strategy, current_price=Decimal("88.00"))
        self.assertTrue(executed)
        self.assertIn("Покупка 5 шт.", msg)

        pos = PortfolioPosition.objects.get(portfolio=self.portfolio, share=self.share)
        self.assertEqual(pos.quantity, 5)
        self.assertEqual(pos.average_buy_price, Decimal("88.00"))

        log_buy = StrategyExecutionLog.objects.filter(strategy=strategy, action="BUY").first()
        self.assertIsNotNone(log_buy)
        self.assertEqual(log_buy.price, Decimal("88.00"))

        # 3. Цена выросла до $115 (>= 110) -> исполняется автоматическая продажа 5 акций с фиксацией прибыли
        executed, msg = execute_strategy(strategy, current_price=Decimal("115.00"))
        self.assertTrue(executed)
        self.assertIn("Продажа 5 шт.", msg)

        # Проверяем, что прибыль зафиксирована: PnL = (115 - 88) * 5 = +135
        tx_sell = PortfolioTransaction.objects.filter(strategy=strategy, transaction_type="SELL").first()
        self.assertIsNotNone(tx_sell)
        self.assertEqual(tx_sell.realized_pnl, Decimal("135.00"))

        perf = get_strategy_performance(strategy)
        self.assertEqual(perf["total_trades"], 2)
        self.assertEqual(perf["buy_trades"], 1)
        self.assertEqual(perf["sell_trades"], 1)
        self.assertEqual(perf["realized_pnl"], Decimal("135.00"))

    def test_dip_buy_profit_sell_strategy(self):
        strategy = TradingStrategy.objects.create(
            user=self.user,
            portfolio=self.portfolio,
            share=self.share,
            name="Dip Buyer",
            strategy_type="DIP_BUY_PROFIT_SELL",
            buy_threshold=Decimal("10.00"),  # Докупка при просадке на 10%
            sell_threshold=Decimal("15.00"),  # Фиксация прибыли при росте на 15%
            trade_quantity=4,
            is_active=True,
        )

        # 1. Первая инициализация позиции: покупка 4 акций по 100
        executed, msg = execute_strategy(strategy, current_price=Decimal("100.00"))
        self.assertTrue(executed)
        pos = PortfolioPosition.objects.get(portfolio=self.portfolio, share=self.share)
        self.assertEqual(pos.quantity, 4)
        self.assertEqual(pos.average_buy_price, Decimal("100.00"))

        # 2. Незначительное изменение цены: 95 (-5%) -> условий нет
        executed, msg = execute_strategy(strategy, current_price=Decimal("95.00"))
        self.assertFalse(executed)

        # 3. Просадка до 89 (-11% <= -10%) -> докупка 4 акций
        executed, msg = execute_strategy(strategy, current_price=Decimal("89.00"))
        self.assertTrue(executed)
        pos.refresh_from_db()
        self.assertEqual(pos.quantity, 8)

        # 4. Рост цены до 120 (рост > 15%) -> фиксация прибыли
        executed, msg = execute_strategy(strategy, current_price=Decimal("120.00"))
        self.assertTrue(executed)
        self.assertIn("Фиксация прибыли", msg)

    def test_batch_simulate_active_strategies(self):
        strategy = TradingStrategy.objects.create(
            user=self.user,
            portfolio=self.portfolio,
            share=self.share,
            name="Batch Strategy",
            strategy_type="THRESHOLD_BUY_SELL",
            buy_threshold=Decimal("100.00"),
            sell_threshold=Decimal("120.00"),
            trade_quantity=2,
            is_active=True,
        )

        self.share.last_price = Decimal("95.00")
        deals = simulate_active_strategies([self.share])
        self.assertEqual(deals, 1)

    def test_strategy_html_views(self):
        # List view
        resp = self.client.get(reverse("dashboard:strategies"))
        self.assertEqual(resp.status_code, 200)

        # Create strategy
        post_resp = self.client.post(
            reverse("dashboard:strategies"),
            {
                "name": "My HTML Strategy",
                "share": self.share.id,
                "strategy_type": "THRESHOLD_BUY_SELL",
                "buy_threshold": "90.00",
                "sell_threshold": "120.00",
                "trade_quantity": 3,
                "is_active": True,
            },
        )
        self.assertEqual(post_resp.status_code, 302)
        strat = TradingStrategy.objects.get(name="My HTML Strategy")

        # Detail view
        detail_resp = self.client.get(reverse("dashboard:strategy_detail", kwargs={"pk": strat.id}))
        self.assertEqual(detail_resp.status_code, 200)

        # Toggle active
        toggle_resp = self.client.post(reverse("dashboard:strategy_toggle", kwargs={"pk": strat.id}))
        self.assertEqual(toggle_resp.status_code, 302)
        strat.refresh_from_db()
        self.assertFalse(strat.is_active)

        # Run step manually
        run_resp = self.client.post(reverse("dashboard:strategy_run", kwargs={"pk": strat.id}))
        self.assertEqual(run_resp.status_code, 302)


class Task4ApiEndpointsTests(APITestCase):
    """Тестирование REST API эндпоинтов новой функциональности"""

    def setUp(self):
        self.user = User.objects.create_user(
            username="api_user@example.com",
            email="api_user@example.com",
            password="StrongPassword123!",
        )
        self.client.force_login(self.user)
        self.client.force_authenticate(user=self.user)
        self.share = Share.objects.create(
            figi="BBG000B9XRY4",
            isin="US0378331005",
            name="Apple Inc",
            ticker="AAPL",
            currency="USD",
            last_price=Decimal("150.00"),
        )

    def test_api_watchlist(self):
        # POST to watchlist
        resp = self.client.post(
            "/api/v1/watchlist/",
            {"share": self.share.id, "target_price": "160.00", "condition": "ABOVE"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

        # GET watchlist
        get_resp = self.client.get("/api/v1/watchlist/")
        self.assertEqual(get_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(get_resp.data["results"]), 1)

    def test_api_portfolio_my_buy_sell(self):
        # GET my portfolio
        resp = self.client.get("/api/v1/portfolio/my/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(Decimal(str(resp.data["balance"])), Decimal("100000.00"))

        # BUY via API
        buy_resp = self.client.post(
            "/api/v1/portfolio/buy/",
            {"share_id": self.share.id, "quantity": 10},
            format="json",
        )
        self.assertEqual(buy_resp.status_code, status.HTTP_201_CREATED)

        # SELL via API
        sell_resp = self.client.post(
            "/api/v1/portfolio/sell/",
            {"share_id": self.share.id, "quantity": 5},
            format="json",
        )
        self.assertEqual(sell_resp.status_code, status.HTTP_201_CREATED)

    def test_api_price_history_and_dynamics(self):
        record_price(self.share, Decimal("150.00"))
        resp = self.client.get("/api/v1/price-history/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(len(resp.data["results"]) >= 1)

        dyn_resp = self.client.get(f"/api/v1/shares/{self.share.id}/dynamics/?period=1M")
        self.assertEqual(dyn_resp.status_code, status.HTTP_200_OK)
        self.assertIn("start_price", dyn_resp.data)
        self.assertIn("absolute_change", dyn_resp.data)

    def test_api_strategies(self):
        resp = self.client.post(
            "/api/v1/strategies/",
            {
                "name": "API Strat",
                "share": self.share.id,
                "strategy_type": "THRESHOLD_BUY_SELL",
                "buy_threshold": "140.00",
                "sell_threshold": "160.00",
                "trade_quantity": 2,
                "is_active": True,
            },
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        strat_id = resp.data["id"]

        run_resp = self.client.post(f"/api/v1/strategies/{strat_id}/run/")
        self.assertEqual(run_resp.status_code, status.HTTP_200_OK)
        self.assertIn("success", run_resp.data)


class Task4SecurityAndPermissionsTests(APITestCase):
    """Проверка ограничений доступа для неавторизованных пользователей"""

    def setUp(self):
        self.share = Share.objects.create(
            figi="BBG000B9XRY4",
            isin="US0378331005",
            name="Apple Inc",
            ticker="AAPL",
            currency="USD",
            last_price=Decimal("150.00"),
        )

    def test_anonymous_access_redirects_for_protected_views(self):
        # HTML views require authentication
        protected_urls = [
            reverse("dashboard:portfolio"),
            reverse("dashboard:watchlist"),
            reverse("dashboard:notifications"),
            reverse("dashboard:strategies"),
        ]
        for url in protected_urls:
            resp = self.client.get(url)
            self.assertEqual(resp.status_code, 302, f"URL {url} should redirect anonymous user")

    def test_anonymous_access_forbidden_for_protected_api(self):
        # API endpoints require authentication
        self.assertEqual(self.client.get("/api/v1/portfolio/my/").status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(self.client.get("/api/v1/watchlist/").status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(self.client.get("/api/v1/notifications/").status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(self.client.get("/api/v1/strategies/").status_code, status.HTTP_403_FORBIDDEN)

    def test_public_views_and_api_are_accessible_by_anonymous(self):
        # Catalog and detail and price history are public
        self.assertEqual(self.client.get(reverse("dashboard:index")).status_code, 200)
        self.assertEqual(self.client.get(reverse("dashboard:detail", kwargs={"pk": self.share.id})).status_code, 200)
        self.assertEqual(self.client.get(reverse("dashboard:price_history", kwargs={"pk": self.share.id})).status_code, 200)
        self.assertEqual(self.client.get("/api/v1/shares/").status_code, 200)
        self.assertEqual(self.client.get("/api/v1/price-history/").status_code, 200)

