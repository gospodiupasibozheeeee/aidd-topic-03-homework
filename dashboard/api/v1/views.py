import re

from django_filters import rest_framework as filters
from rest_framework import viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.filters import OrderingFilter, SearchFilter

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
