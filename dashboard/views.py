import logging

from django.contrib.auth.mixins import UserPassesTestMixin
from django.db.models.deletion import ProtectedError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, ListView, UpdateView, View

from .forms import ShareModelForm
from .models import Share
from .services.client import MarketDataError
from .services.graph import get_graph

logger = logging.getLogger("main")


class IsUserAuthenticatedMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_authenticated

    @staticmethod
    def handle_no_permission():
        return redirect("dashboard:index")


class ShareListView(ListView):
    """Список акций"""

    model = Share
    template_name = "dashboard/list.html"
    paginate_by = 100
    ordering = ["name"]


class ShareDetailView(View):
    @staticmethod
    def get(request, pk):
        share = get_object_or_404(Share, pk=pk)
        try:
            graph = get_graph(share)
            graph_error = "" if graph else "За выбранный период нет рыночных данных."
        except MarketDataError as exc:
            logger.warning("Graph unavailable for share %s: %s", share.pk, exc)
            graph = ""
            graph_error = "Рыночные данные временно недоступны. Попробуйте позже."

        return render(
            request,
            "dashboard/detail.html",
            {"plot_div": graph, "graph_error": graph_error, "share": share},
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

    def form_valid(self, form):
        try:
            return super().form_valid(form)
        except ProtectedError:
            form.add_error(
                None,
                "Акция используется портфелем или стратегией и не может быть удалена.",
            )
            return self.render_to_response(self.get_context_data(form=form), status=409)
