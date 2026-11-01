import uuid
from datetime import date, timedelta

from django import forms
from django.utils import timezone

from dashboard.models import Share

from .models import QUANTUM, Portfolio, Strategy, WatchItem, Watchlist


class StyledFormMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if not isinstance(field.widget, forms.HiddenInput):
                field.widget.attrs.setdefault("class", "form-control")


class WatchlistForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Watchlist
        fields = ("name",)


class WatchItemForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = WatchItem
        fields = ("share", "direction", "target")
        labels = {"share": "Акция"}
        help_texts = {"target": "Оставьте пустым, чтобы отключить уведомления."}


class PortfolioForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Portfolio
        fields = ("name", "currency", "initial_cash")


class TradeForm(StyledFormMixin, forms.Form):
    share = forms.ModelChoiceField(
        queryset=Share.objects.order_by("name"), label="Акция"
    )
    side = forms.ChoiceField(choices=Strategy.Action, label="Операция")
    quantity = forms.IntegerField(min_value=1, max_value=2147483647, label="Количество")
    price = forms.DecimalField(
        max_digits=24,
        decimal_places=9,
        min_value=QUANTUM,
        required=False,
        label="Цена",
        help_text="Пусто — использовать сохранённую котировку.",
    )
    request_id = forms.UUIDField(initial=uuid.uuid4, widget=forms.HiddenInput)


class StrategyForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Strategy
        fields = (
            "name",
            "portfolio",
            "share",
            "quantity",
            "buy_below",
            "sell_above",
            "active",
        )
        labels = {"portfolio": "Портфель", "share": "Акция"}

    def __init__(self, *args, owner, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["portfolio"].queryset = Portfolio.objects.filter(owner=owner)
        self.fields["share"].queryset = Share.objects.order_by("name")
        if self.instance.pk:
            self.fields["portfolio"].disabled = self.fields["share"].disabled = True


class HistoryRangeForm(StyledFormMixin, forms.Form):
    start = forms.DateField(
        required=False,
        label="С даты (UTC)",
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    end = forms.DateField(
        required=False,
        label="По дату (UTC)",
        widget=forms.DateInput(attrs={"type": "date"}),
    )

    def clean(self):
        values = super().clean()
        end = values.get("end") or timezone.now().date()
        start = values.get("start") or (
            end - timedelta(days=30) if end.toordinal() > 30 else date.min
        )
        if start > end:
            raise forms.ValidationError("Начало периода не может быть позже окончания.")
        values.update(start=start, end=end)
        return values
