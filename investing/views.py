from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from dashboard.models import Share

from .forms import (
    HistoryRangeForm,
    PortfolioForm,
    StrategyForm,
    TradeForm,
    WatchItemForm,
    WatchlistForm,
)
from .models import Notification, Portfolio, Strategy, WatchItem, Watchlist
from .services.history import history_data, history_graph
from .services.monitoring import save_watch_item
from .services.strategies import save_strategy, strategy_summary
from .services.trading import create_portfolio, execute_trade, portfolio_summary


def form_error(form, error):
    message = (
        "; ".join(error.messages)
        if isinstance(error, ValidationError)
        else "Запись с такими данными уже существует."
    )
    form.add_error(None, message)


def form_page(request, form, title):
    return render(request, "investing/form.html", {"form": form, "title": title})


@login_required
def workspace(request):
    strategies = Strategy.objects.filter(portfolio__owner=request.user).select_related(
        "portfolio", "share"
    )
    return render(
        request,
        "investing/workspace.html",
        {
            "watchlists": Watchlist.objects.filter(owner=request.user),
            "portfolios": Portfolio.objects.filter(owner=request.user),
            "strategies": [
                {"rule": item, "stats": strategy_summary(item)} for item in strategies
            ],
            "notifications": Notification.objects.filter(owner=request.user)[:10],
            "unread": Notification.objects.filter(
                owner=request.user, read_at__isnull=True
            ).count(),
        },
    )


@login_required
def watchlist_create(request):
    form = WatchlistForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        item = form.save(commit=False)
        item.owner = request.user
        try:
            with transaction.atomic():
                item.full_clean()
                item.save()
            return redirect("investing:watchlist", pk=item.pk)
        except (ValidationError, IntegrityError) as exc:
            form_error(form, exc)
    return form_page(request, form, "Создать список наблюдения")


@login_required
def watchlist_detail(request, pk):
    watchlist = get_object_or_404(Watchlist, pk=pk, owner=request.user)
    form = WatchItemForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            save_watch_item(request.user, watchlist=watchlist, **form.cleaned_data)
            return redirect("investing:watchlist", pk=pk)
        except (ValidationError, IntegrityError) as exc:
            form_error(form, exc)
    return render(
        request,
        "investing/watchlist.html",
        {
            "watchlist": watchlist,
            "items": watchlist.items.select_related("share"),
            "form": form,
        },
    )


@login_required
def watch_item_edit(request, pk):
    item = get_object_or_404(WatchItem, pk=pk, watchlist__owner=request.user)
    form = WatchItemForm(request.POST or None, instance=item)
    if request.method == "POST" and form.is_valid():
        try:
            save_watch_item(
                request.user, watchlist=item.watchlist, item_id=pk, **form.cleaned_data
            )
            return redirect("investing:watchlist", pk=item.watchlist_id)
        except (ValidationError, IntegrityError) as exc:
            form_error(form, exc)
    return form_page(request, form, "Изменить условие наблюдения")


@login_required
@require_POST
def watch_item_delete(request, pk):
    item = get_object_or_404(WatchItem, pk=pk, watchlist__owner=request.user)
    destination = item.watchlist_id
    item.delete()
    return redirect("investing:watchlist", pk=destination)


@login_required
@require_POST
def watchlist_delete(request, pk):
    get_object_or_404(Watchlist, pk=pk, owner=request.user).delete()
    return redirect("investing:workspace")


@login_required
def notifications(request):
    page = Paginator(Notification.objects.filter(owner=request.user), 50).get_page(
        request.GET.get("page")
    )
    return render(request, "investing/notifications.html", {"page_obj": page})


@login_required
@require_POST
def notification_read(request, pk):
    item = get_object_or_404(Notification, pk=pk, owner=request.user)
    if item.read_at is None:
        item.read_at = timezone.now()
        item.save(update_fields=["read_at"])
    return redirect("investing:notifications")


@login_required
def portfolio_create(request):
    form = PortfolioForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            item = create_portfolio(request.user, **form.cleaned_data)
            return redirect("investing:portfolio", pk=item.pk)
        except (ValidationError, IntegrityError) as exc:
            form_error(form, exc)
    return form_page(request, form, "Создать виртуальный портфель")


@login_required
def portfolio_detail(request, pk):
    item = get_object_or_404(Portfolio, pk=pk, owner=request.user)
    page = Paginator(item.trades.select_related("share"), 50).get_page(
        request.GET.get("page")
    )
    return render(
        request,
        "investing/portfolio.html",
        {
            "portfolio": item,
            "summary": portfolio_summary(item),
            "page_obj": page,
            "runs": item.strategy_runs.select_related("quote", "quote__share", "trade")[
                :50
            ],
        },
    )


@login_required
def trade_create(request, pk):
    portfolio = get_object_or_404(Portfolio, pk=pk, owner=request.user)
    form = TradeForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        values = dict(form.cleaned_data)
        share = values.pop("share")
        try:
            execute_trade(request.user, portfolio.pk, share.pk, **values)
            return redirect("investing:portfolio", pk=pk)
        except (ValidationError, IntegrityError) as exc:
            form_error(form, exc)
    return form_page(request, form, f"Виртуальная сделка: {portfolio.name}")


@login_required
def strategy_edit(request, pk=None):
    instance = (
        get_object_or_404(Strategy, pk=pk, portfolio__owner=request.user)
        if pk is not None
        else None
    )
    form = StrategyForm(request.POST or None, instance=instance, owner=request.user)
    if request.method == "POST" and form.is_valid():
        try:
            save_strategy(request.user, strategy_id=pk, **form.cleaned_data)
            return redirect("investing:workspace")
        except (ValidationError, IntegrityError) as exc:
            form_error(form, exc)
    return form_page(request, form, "Изменить стратегию" if pk else "Создать стратегию")


@login_required
@require_POST
def strategy_delete(request, pk):
    get_object_or_404(Strategy, pk=pk, portfolio__owner=request.user).delete()
    return redirect("investing:workspace")


def price_history(request, pk):
    share = get_object_or_404(Share, pk=pk)
    form = HistoryRangeForm(request.GET)
    context = {"share": share, "form": form}
    if form.is_valid():
        records, summary, daily = history_data(share, **form.cleaned_data)
        context.update(
            summary=summary,
            graph=history_graph(daily),
            page_obj=Paginator(records.order_by("-observed_at", "-pk"), 100).get_page(
                request.GET.get("page")
            ),
        )
    return render(
        request,
        "investing/history.html",
        context,
        status=200 if form.is_valid() else 400,
    )
