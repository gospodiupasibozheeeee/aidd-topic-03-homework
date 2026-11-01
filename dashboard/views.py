from __future__ import annotations

import logging

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    UpdateView,
)

from .forms import ShareModelForm
from .models import Share
from .services.graph import get_graph
from .services.tinkoff import MarketDataError

logger = logging.getLogger("dashboard")


class AuthenticatedRequiredMixin(LoginRequiredMixin):
    """Redirect anonymous users to the catalogue instead of raising 403."""

    login_url = reverse_lazy("dashboard:index")
    redirect_field_name = None


class ShareListView(ListView):
    """Public catalogue of shares."""

    model = Share
    template_name = "dashboard/list.html"
    paginate_by = 100
    ordering = ["name"]


class ShareDetailView(DetailView):
    """Public share card with a 180-day price chart."""

    model = Share
    template_name = "dashboard/detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            context["plot_div"] = get_graph(self.object)
        except MarketDataError as exc:
            logger.warning("Chart unavailable for share %s: %s", self.object.pk, exc)
            context["chart_error"] = str(exc)
        except Exception:
            logger.exception("Unexpected chart error for share %s", self.object.pk)
            context["chart_error"] = "Не удалось построить график. Попробуйте позже."
        return context


class ShareCreateView(AuthenticatedRequiredMixin, CreateView):
    """Create a share through the web form."""

    model = Share
    template_name = "dashboard/create.html"
    form_class = ShareModelForm
    success_url = reverse_lazy("dashboard:index")

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, "Акция добавлена.")
        return response


class ShareUpdateView(AuthenticatedRequiredMixin, UpdateView):
    """Edit an existing share."""

    model = Share
    template_name = "dashboard/create.html"
    form_class = ShareModelForm
    success_url = reverse_lazy("dashboard:index")

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, "Изменения сохранены.")
        return response


class ShareDeleteView(AuthenticatedRequiredMixin, DeleteView):
    """Delete a share after confirmation."""

    model = Share
    template_name = "dashboard/delete.html"
    success_url = reverse_lazy("dashboard:index")

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, "Акция удалена.")
        return response
