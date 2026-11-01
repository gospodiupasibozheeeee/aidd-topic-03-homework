from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import IntegrityError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    UpdateView,
)

from dashboard.models import Share
from investments.forms import (
    PortfolioForm,
    StrategyForm,
    TransactionForm,
    WatchlistForm,
    WatchlistItemForm,
)
from investments.models import (
    Notification,
    Portfolio,
    Strategy,
    Watchlist,
    WatchlistItem,
)
from investments.services.history import PERIODS, history_context
from investments.services.portfolio import (
    current_price,
    portfolio_positions,
    portfolio_summary,
)
from investments.services.strategy import (
    evaluate_strategy,
    reset_strategy,
    strategy_summary,
)
from investments.services.watchlist import unread_count


class OwnedQuerysetMixin(LoginRequiredMixin):
    """Limit generic views to objects owned by the current user."""

    def get_queryset(self):
        return super().get_queryset().filter(user=self.request.user)


class PortfolioListView(OwnedQuerysetMixin, ListView):
    model = Portfolio
    template_name = "investments/portfolio_list.html"
    context_object_name = "portfolios"


class PortfolioCreateView(OwnedQuerysetMixin, CreateView):
    model = Portfolio
    form_class = PortfolioForm
    template_name = "investments/form.html"

    def form_valid(self, form):
        form.instance.user = self.request.user
        try:
            response = super().form_valid(form)
        except IntegrityError:
            form.add_error("name", "Портфель с таким названием уже существует.")
            return self.form_invalid(form)
        messages.success(self.request, "Портфель создан.")
        return response

    def get_success_url(self):
        return reverse("investments:portfolio-detail", args=[self.object.pk])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Новый портфель"
        context["cancel_url"] = reverse("investments:portfolio-list")
        return context


class PortfolioDeleteView(OwnedQuerysetMixin, DeleteView):
    model = Portfolio
    template_name = "investments/confirm_delete.html"
    success_url = reverse_lazy("investments:portfolio-list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Удаление портфеля"
        context["cancel_url"] = reverse(
            "investments:portfolio-detail", args=[self.object.pk]
        )
        return context


class PortfolioDetailView(OwnedQuerysetMixin, DetailView):
    model = Portfolio
    template_name = "investments/portfolio_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["positions"] = portfolio_positions(self.object)
        context["summary"] = portfolio_summary(self.object)
        context["transactions"] = self.object.transactions.select_related("share")
        context["form"] = kwargs.get("form") or TransactionForm(portfolio=self.object)
        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = TransactionForm(request.POST, portfolio=self.object)
        if form.is_valid():
            transaction = form.save(commit=False)
            transaction.portfolio = self.object
            transaction.save()
            messages.success(
                request,
                f"Операция сохранена: {transaction.get_side_display()} "
                f"{transaction.quantity} {transaction.share.ticker}.",
            )
            return redirect("investments:portfolio-detail", pk=self.object.pk)
        return self.render_to_response(self.get_context_data(form=form))


class WatchlistListView(OwnedQuerysetMixin, ListView):
    model = Watchlist
    template_name = "investments/watchlist_list.html"
    context_object_name = "watchlists"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["unread_count"] = unread_count(self.request.user)
        return context


class WatchlistCreateView(OwnedQuerysetMixin, CreateView):
    model = Watchlist
    form_class = WatchlistForm
    template_name = "investments/form.html"

    def form_valid(self, form):
        form.instance.user = self.request.user
        try:
            response = super().form_valid(form)
        except IntegrityError:
            form.add_error("name", "Список с таким названием уже существует.")
            return self.form_invalid(form)
        messages.success(self.request, "Список наблюдения создан.")
        return response

    def get_success_url(self):
        return reverse("investments:watchlist-detail", args=[self.object.pk])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Новый список наблюдения"
        context["cancel_url"] = reverse("investments:watchlist-list")
        return context


class WatchlistDetailView(OwnedQuerysetMixin, DetailView):
    model = Watchlist
    template_name = "investments/watchlist_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["items"] = self.object.items.select_related("share")
        context["form"] = kwargs.get("form") or WatchlistItemForm()
        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = WatchlistItemForm(request.POST)
        if form.is_valid():
            item = form.save(commit=False)
            item.watchlist = self.object
            try:
                item.save()
            except IntegrityError:
                form.add_error("share", "Эта акция уже есть в списке.")
            else:
                messages.success(request, "Акция добавлена в наблюдение.")
                return redirect("investments:watchlist-detail", pk=self.object.pk)
        return self.render_to_response(self.get_context_data(form=form))


class WatchlistItemDeleteView(LoginRequiredMixin, View):
    def post(self, request, pk, item_pk):
        item = get_object_or_404(
            WatchlistItem,
            pk=item_pk,
            watchlist_id=pk,
            watchlist__user=request.user,
        )
        item.delete()
        messages.success(request, "Акция удалена из наблюдения.")
        return redirect("investments:watchlist-detail", pk=pk)


class NotificationListView(LoginRequiredMixin, ListView):
    model = Notification
    template_name = "investments/notifications.html"
    context_object_name = "notifications"

    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["unread_count"] = unread_count(self.request.user)
        return context


class NotificationReadView(LoginRequiredMixin, View):
    def post(self, request, pk):
        notification = get_object_or_404(Notification, pk=pk, user=request.user)
        notification.is_read = True
        notification.save(update_fields=["is_read"])
        return redirect("investments:notifications")


class StrategyListView(OwnedQuerysetMixin, ListView):
    model = Strategy
    template_name = "investments/strategy_list.html"
    context_object_name = "strategies"


class StrategyCreateView(OwnedQuerysetMixin, CreateView):
    model = Strategy
    form_class = StrategyForm
    template_name = "investments/form.html"

    def form_valid(self, form):
        form.instance.user = self.request.user
        try:
            response = super().form_valid(form)
        except IntegrityError:
            form.add_error("name", "Стратегия с таким названием уже существует.")
            return self.form_invalid(form)
        messages.success(self.request, "Стратегия создана.")
        return response

    def get_success_url(self):
        return reverse("investments:strategy-detail", args=[self.object.pk])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Новая стратегия"
        context["cancel_url"] = reverse("investments:strategy-list")
        return context


class StrategyUpdateView(OwnedQuerysetMixin, UpdateView):
    model = Strategy
    form_class = StrategyForm
    template_name = "investments/form.html"

    def form_valid(self, form):
        try:
            response = super().form_valid(form)
        except IntegrityError:
            form.add_error("name", "Стратегия с таким названием уже существует.")
            return self.form_invalid(form)
        messages.success(self.request, "Стратегия сохранена.")
        return response

    def get_success_url(self):
        return reverse("investments:strategy-detail", args=[self.object.pk])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Редактирование стратегии"
        context["cancel_url"] = reverse(
            "investments:strategy-detail", args=[self.object.pk]
        )
        return context


class StrategyDeleteView(OwnedQuerysetMixin, DeleteView):
    model = Strategy
    template_name = "investments/confirm_delete.html"
    success_url = reverse_lazy("investments:strategy-list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Удаление стратегии"
        context["cancel_url"] = reverse(
            "investments:strategy-detail", args=[self.object.pk]
        )
        return context


class StrategyDetailView(OwnedQuerysetMixin, DetailView):
    model = Strategy
    template_name = "investments/strategy_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["summary"] = strategy_summary(self.object)
        context["trades"] = self.object.trades.all()
        return context


class StrategyEvaluateView(LoginRequiredMixin, View):
    def post(self, request, pk):
        strategy = get_object_or_404(Strategy, pk=pk, user=request.user)
        price = current_price(strategy.share)
        if price is None:
            messages.error(request, "Для акции ещё нет рыночной цены.")
        else:
            trade = evaluate_strategy(strategy, price)
            if trade is None:
                messages.info(request, "Условия стратегии не выполнены.")
            else:
                messages.success(
                    request,
                    f"Симуляция: {trade.get_side_display()} "
                    f"{trade.quantity} {strategy.share.ticker} по {trade.price:.2f}.",
                )
        return redirect("investments:strategy-detail", pk=pk)


class StrategyResetView(LoginRequiredMixin, View):
    def post(self, request, pk):
        strategy = get_object_or_404(Strategy, pk=pk, user=request.user)
        reset_strategy(strategy)
        messages.success(request, "Стратегия сброшена к начальному состоянию.")
        return redirect("investments:strategy-detail", pk=pk)


def price_history(request, pk):
    share = get_object_or_404(Share, pk=pk)
    try:
        period = int(request.GET.get("period", 30))
    except (TypeError, ValueError):
        period = 30
    if period not in PERIODS:
        period = 30
    context = history_context(share, period)
    return render(request, "investments/price_history.html", context)
