import re

from django.db.models.deletion import ProtectedError
from django_filters import rest_framework as filters
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response

from dashboard.models import Share

from .serializer import ShareSerializer


class ShareFilter(filters.FilterSet):
    class Meta:
        model = Share
        fields = ("name", "ticker")


class ValidatedSearchFilter(SearchFilter):
    def filter_queryset(self, request, queryset, view):
        for term in self.get_search_terms(request):
            try:
                re.compile(term)
            except re.error as exc:
                raise ValidationError(
                    {"search": "Некорректное регулярное выражение."}
                ) from exc
        return super().filter_queryset(request, queryset, view)


class ShareViewSet(viewsets.ModelViewSet):
    serializer_class = ShareSerializer
    queryset = Share.objects.order_by("name", "id")
    filter_backends = (
        OrderingFilter,
        filters.DjangoFilterBackend,
        ValidatedSearchFilter,
    )
    filterset_class = ShareFilter
    ordering_fields = ["name", "ticker"]
    search_fields = ["$name"]

    @action(detail=True, methods=["get"])
    def history(self, request, pk=None):
        from investing.api import price_history_response

        return price_history_response(self, request, self.get_object())

    def destroy(self, request, *args, **kwargs):
        try:
            return super().destroy(request, *args, **kwargs)
        except ProtectedError:
            return Response(
                {
                    "detail": "Акция используется портфелем или стратегией и не может быть удалена."
                },
                status=409,
            )
