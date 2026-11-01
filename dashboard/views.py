from decimal import Decimal
import logging
from typing import Optional

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db import IntegrityError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.views.generic import CreateView, DeleteView, ListView, UpdateView, View

from .forms import (
    PortfolioTradeForm,
    ShareModelForm,
    TradingStrategyForm,
    WatchlistForm,
)
from .models import (
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
from .services.graph import get_graph
from .services.history_service import (
    calculate_price_dynamics,
    generate_history_chart,
    get_price_history,
)
from .services.portfolio_service import buy_share, get_or_create_portfolio, sell_share
from .services.strategy_service import execute_strategy, get_strategy_performance

logger = logging.getLogger("main")


class IsUserAuthenticatedMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_authenticated

    @staticmethod
    def handle_no_permission():
        return redirect("dashboard:index")


# ==============================================================================
# Каталог акций и карточка
# ==============================================================================


class ShareListView(ListView):
    """Список акций"""

    model = Share
    template_name = "dashboard/list.html"
    paginate_by = 100
    ordering = ["name"]


class ShareDetailView(View):
    """Карточка акции с историческим графиком, аналитикой динамики и быстрыми действиями"""

    def get(self, request, pk):
        share = get_object_or_404(Share, id=pk)
        period = request.GET.get("period", "1M").upper()
        if period not in ["1D", "1W", "1M", "1Y", "ALL"]:
            period = "1M"

        # График динамики на основе накопленной истории PriceHistory (Задание 4.3)
        try:
            history_chart = generate_history_chart(share, period=period)
        except Exception as e:
            logger.error(f"Ошибка построения графика истории {share.ticker}: {e}")
            history_chart = "<div class='alert alert-warning'>График истории временно недоступен</div>"

        # Расчет показателей динамики (Задание 4.3)
        dynamics = calculate_price_dynamics(share, period=period)

        # График из Tinkoff API (исходная логика)
        try:
            candle_chart = get_graph(share)
        except Exception as e:
            candle_chart = None

        watchlist_form = None
        trade_form = None
        user_in_watchlist = False

        if request.user.is_authenticated:
            watchlist_form = WatchlistForm(
                initial={"share": share, "target_price": share.last_price or Decimal("100.00")}
            )
            trade_form = PortfolioTradeForm(initial={"share": share, "quantity": 1})
            user_in_watchlist = WatchlistItem.objects.filter(
                user=request.user, share=share
            ).exists()

        return render(
            request,
            "dashboard/detail.html",
            {
                "share": share,
                "history_chart": history_chart,
                "candle_chart": candle_chart,
                "dynamics": dynamics,
                "period": period,
                "watchlist_form": watchlist_form,
                "trade_form": trade_form,
                "user_in_watchlist": user_in_watchlist,
            },
        )


class ShareCreateView(IsUserAuthenticatedMixin, CreateView):
    """Добавление инструмента"""

    template_name = "dashboard/create.html"
    form_class = ShareModelForm
    success_url = reverse_lazy("dashboard:index")


class ShareUpdateView(IsUserAuthenticatedMixin, UpdateView):
    """Редактирование инструмента"""

    model = Share
    template_name = "dashboard/create.html"
    form_class = ShareModelForm
    success_url = reverse_lazy("dashboard:index")


class ShareDeleteView(IsUserAuthenticatedMixin, DeleteView):
    """Удаление инструмента"""

    model = Share
    template_name = "dashboard/delete.html"
    success_url = reverse_lazy("dashboard:index")


# ==============================================================================
# Задание 4.1. Персональный мониторинг акций и уведомления
# ==============================================================================


class WatchlistListView(LoginRequiredMixin, View):
    """Список наблюдения и настройка персональных уведомлений"""

    def get(self, request):
        items = WatchlistItem.objects.filter(user=request.user).select_related("share")
        form = WatchlistForm()
        return render(
            request,
            "dashboard/watchlist_list.html",
            {"watchlist_items": items, "form": form},
        )

    def post(self, request):
        form = WatchlistForm(request.POST)
        if form.is_valid():
            share = form.cleaned_data["share"]
            target_price = form.cleaned_data["target_price"]
            condition = form.cleaned_data["condition"]

            item, created = WatchlistItem.objects.update_or_create(
                user=request.user,
                share=share,
                condition=condition,
                defaults={
                    "target_price": target_price,
                    "is_active": True,
                    "is_triggered": False,
                },
            )
            action_text = "добавлена в список наблюдения" if created else "обновлена"
            messages.success(
                request,
                f"Акция {share.ticker} {action_text} с порогом {target_price} ({item.get_condition_display()}).",
            )
            return redirect("dashboard:watchlist")

        items = WatchlistItem.objects.filter(user=request.user).select_related("share")
        return render(
            request,
            "dashboard/watchlist_list.html",
            {"watchlist_items": items, "form": form},
        )


class WatchlistDeleteView(LoginRequiredMixin, View):
    """Удаление акции из списка наблюдения"""

    def post(self, request, pk):
        item = get_object_or_404(WatchlistItem, id=pk, user=request.user)
        ticker = item.share.ticker
        item.delete()
        messages.info(request, f"Акция {ticker} удалена из списка наблюдения.")
        return redirect("dashboard:watchlist")


class NotificationListView(LoginRequiredMixin, ListView):
    """Список уведомлений пользователя"""

    model = PriceNotification
    template_name = "dashboard/notification_list.html"
    context_object_name = "notifications"
    paginate_by = 50

    def get_queryset(self):
        return PriceNotification.objects.filter(user=self.request.user).select_related("share")


class NotificationMarkReadView(LoginRequiredMixin, View):
    """Отметка уведомлений как прочитанных"""

    def post(self, request, pk=None):
        if pk:
            notification = get_object_or_404(PriceNotification, id=pk, user=request.user)
            notification.is_read = True
            notification.save(update_fields=["is_read"])
        else:
            PriceNotification.objects.filter(user=request.user, is_read=False).update(
                is_read=True
            )
            messages.success(request, "Все уведомления отмечены как прочитанные.")
        return redirect("dashboard:notifications")


# ==============================================================================
# Задание 4.2. Виртуальный инвестиционный портфель
# ==============================================================================


class PortfolioDashboardView(LoginRequiredMixin, View):
    """Панель управления виртуальным инвестиционным портфелем"""

    def get(self, request):
        portfolio = get_or_create_portfolio(request.user)
        positions = (
            PortfolioPosition.objects.filter(portfolio=portfolio, quantity__gt=0)
            .select_related("share")
            .order_by("share__ticker")
        )
        transactions = (
            PortfolioTransaction.objects.filter(portfolio=portfolio)
            .select_related("share")
            .order_by("-created_at")[:50]
        )
        form = PortfolioTradeForm()

        return render(
            request,
            "dashboard/portfolio.html",
            {
                "portfolio": portfolio,
                "positions": positions,
                "transactions": transactions,
                "form": form,
            },
        )


class PortfolioTradeView(LoginRequiredMixin, View):
    """Исполнение виртуальной сделки покупки / продажи"""

    def post(self, request):
        form = PortfolioTradeForm(request.POST)
        if not form.is_valid():
            messages.error(request, "Некорректно заполнены параметры сделки.")
            return redirect("dashboard:portfolio")

        action = form.cleaned_data["action"]
        share = form.cleaned_data["share"]
        quantity = form.cleaned_data["quantity"]

        portfolio = get_or_create_portfolio(request.user)

        if action == "BUY":
            tx, err = buy_share(portfolio=portfolio, share=share, quantity=quantity)
            if tx:
                messages.success(
                    request,
                    f"Успешная покупка: {quantity} шт. {share.ticker} по {tx.price} {share.currency} на сумму {tx.total_amount}.",
                )
            else:
                messages.error(request, f"Ошибка при покупке: {err}")
        elif action == "SELL":
            tx, err = sell_share(portfolio=portfolio, share=share, quantity=quantity)
            if tx:
                messages.success(
                    request,
                    f"Успешная продажа: {quantity} шт. {share.ticker} по {tx.price} {share.currency}. Выручка: {tx.total_amount}, реализованный PnL: {tx.realized_pnl}.",
                )
            else:
                messages.error(request, f"Ошибка при продаже: {err}")

        # Если был передан next_url, редиректим туда, иначе в портфель
        next_url = request.POST.get("next") or reverse("dashboard:portfolio")
        return redirect(next_url)


# ==============================================================================
# Задание 4.3. История изменения рыночных цен и динамика
# ==============================================================================


class SharePriceHistoryView(View):
    """Детальный просмотр истории цен и динамики котировок акции"""

    def get(self, request, pk):
        share = get_object_or_404(Share, id=pk)
        period = request.GET.get("period", "1M").upper()
        if period not in ["1D", "1W", "1M", "1Y", "ALL"]:
            period = "1M"

        history_records = list(get_price_history(share, period=period))
        dynamics = calculate_price_dynamics(share, period=period)
        chart_div = generate_history_chart(share, period=period)

        return render(
            request,
            "dashboard/price_history.html",
            {
                "share": share,
                "period": period,
                "history_records": history_records,
                "dynamics": dynamics,
                "chart_div": chart_div,
            },
        )


# ==============================================================================
# Задание 4.4. Симулятор инвестиционных стратегий
# ==============================================================================


class StrategyListView(LoginRequiredMixin, View):
    """Список стратегий пользователя и форма создания"""

    def get(self, request):
        portfolio = get_or_create_portfolio(request.user)
        strategies = TradingStrategy.objects.filter(user=request.user).select_related(
            "share", "portfolio"
        )
        form = TradingStrategyForm()
        return render(
            request,
            "dashboard/strategy_list.html",
            {
                "strategies": strategies,
                "form": form,
                "portfolio": portfolio,
            },
        )

    def post(self, request):
        portfolio = get_or_create_portfolio(request.user)
        form = TradingStrategyForm(request.POST)
        if form.is_valid():
            strategy = form.save(commit=False)
            strategy.user = request.user
            strategy.portfolio = portfolio
            strategy.save()
            messages.success(request, f"Стратегия «{strategy.name}» успешно создана!")
            return redirect("dashboard:strategies")

        strategies = TradingStrategy.objects.filter(user=request.user).select_related(
            "share", "portfolio"
        )
        return render(
            request,
            "dashboard/strategy_list.html",
            {
                "strategies": strategies,
                "form": form,
                "portfolio": portfolio,
            },
        )


class StrategyDetailView(LoginRequiredMixin, View):
    """Детальный просмотр стратегии, метрики эффективности и лог исполнения"""

    def get(self, request, pk):
        strategy = get_object_or_404(
            TradingStrategy.objects.select_related("share", "portfolio"),
            id=pk,
            user=request.user,
        )
        logs = StrategyExecutionLog.objects.filter(strategy=strategy).order_by("-executed_at")[
            :100
        ]
        performance = get_strategy_performance(strategy)

        return render(
            request,
            "dashboard/strategy_detail.html",
            {
                "strategy": strategy,
                "logs": logs,
                "performance": performance,
            },
        )


class StrategyRunView(LoginRequiredMixin, View):
    """Ручной запуск шага симуляции стратегии"""

    def post(self, request, pk):
        strategy = get_object_or_404(TradingStrategy, id=pk, user=request.user)
        success, msg = execute_strategy(strategy)
        if success:
            messages.success(request, f"Симуляция выполнена: {msg}")
        else:
            messages.info(request, f"Результат проверки: {msg}")
        return redirect("dashboard:strategy_detail", pk=strategy.id)


class StrategyToggleActiveView(LoginRequiredMixin, View):
    """Включение / отключение стратегии"""

    def post(self, request, pk):
        strategy = get_object_or_404(TradingStrategy, id=pk, user=request.user)
        strategy.is_active = not strategy.is_active
        strategy.save(update_fields=["is_active"])
        status = "активирована" if strategy.is_active else "приостановлена"
        messages.info(request, f"Стратегия «{strategy.name}» {status}.")
        return redirect("dashboard:strategies")


class StrategyDeleteView(LoginRequiredMixin, View):
    """Удаление стратегии"""

    def post(self, request, pk):
        strategy = get_object_or_404(TradingStrategy, id=pk, user=request.user)
        name = strategy.name
        strategy.delete()
        messages.info(request, f"Стратегия «{name}» удалена.")
        return redirect("dashboard:strategies")
