from __future__ import annotations

from django import forms

from dashboard.models import Share
from investments.models import (
    Portfolio,
    Strategy,
    Transaction,
    Watchlist,
    WatchlistItem,
)
from investments.services.portfolio import PortfolioError, validate_transaction


class BootstrapFormMixin:
    """Apply Bootstrap 5 classes to all widgets."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, forms.CheckboxInput):
                widget.attrs.setdefault("class", "form-check-input")
            elif isinstance(widget, forms.Select):
                widget.attrs.setdefault("class", "form-select")
            else:
                widget.attrs.setdefault("class", "form-control")


class PortfolioForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Portfolio
        fields = ("name",)
        widgets = {"name": forms.TextInput(attrs={"placeholder": "Например, Основной"})}


class TransactionForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Transaction
        fields = ("share", "side", "quantity", "price", "note")
        labels = {
            "share": "Акция",
            "side": "Тип операции",
            "quantity": "Количество",
            "price": "Цена",
            "note": "Комментарий",
        }

    def __init__(self, *args, portfolio: Portfolio | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.portfolio = portfolio
        self.fields["share"].queryset = Share.objects.order_by("name")
        self.fields["quantity"].initial = 1
        self.fields["price"].widget.attrs.update({"step": "0.000000001", "min": "0"})

    def clean(self):
        cleaned_data = super().clean()
        if self.portfolio is None:
            return cleaned_data

        try:
            validate_transaction(
                self.portfolio,
                cleaned_data.get("share"),
                cleaned_data.get("side"),
                cleaned_data.get("quantity"),
            )
        except PortfolioError as exc:
            self.add_error("quantity", str(exc))
        return cleaned_data


class WatchlistForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Watchlist
        fields = ("name",)
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "Например, Дивидендные"})
        }


class WatchlistItemForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = WatchlistItem
        fields = ("share", "target_price", "direction", "is_active")
        labels = {
            "share": "Акция",
            "target_price": "Целевая цена",
            "direction": "Условие",
            "is_active": "Активно",
        }
        widgets = {
            "target_price": forms.NumberInput(
                attrs={
                    "step": "0.000000001",
                    "min": "0",
                    "placeholder": "Необязательно",
                }
            )
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["share"].queryset = Share.objects.order_by("name")

    def clean_target_price(self):
        value = self.cleaned_data.get("target_price")
        if value is not None and value <= 0:
            raise forms.ValidationError("Целевая цена должна быть положительной.")
        return value


class StrategyForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Strategy
        fields = (
            "name",
            "share",
            "buy_below",
            "sell_above",
            "quantity",
            "initial_cash",
            "is_active",
        )
        widgets = {
            "buy_below": forms.NumberInput(attrs={"step": "0.000000001", "min": "0"}),
            "sell_above": forms.NumberInput(attrs={"step": "0.000000001", "min": "0"}),
            "quantity": forms.NumberInput(attrs={"step": "0.00000001", "min": "0"}),
            "initial_cash": forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["share"].queryset = Share.objects.order_by("name")

    def clean(self):
        cleaned_data = super().clean()
        buy_below = cleaned_data.get("buy_below")
        sell_above = cleaned_data.get("sell_above")
        quantity = cleaned_data.get("quantity")
        initial_cash = cleaned_data.get("initial_cash")

        if buy_below is not None and sell_above is not None:
            if buy_below >= sell_above:
                self.add_error(
                    "sell_above", "Цена продажи должна быть выше цены покупки."
                )
        if quantity is not None and quantity <= 0:
            self.add_error("quantity", "Количество должно быть положительным.")
        if initial_cash is not None and initial_cash <= 0:
            self.add_error(
                "initial_cash", "Начальный капитал должен быть положительным."
            )
        return cleaned_data

    def save(self, commit: bool = True):
        strategy = super().save(commit=False)
        if strategy.pk is None:
            strategy.cash = strategy.initial_cash
        if commit:
            strategy.save()
            self.save_m2m()
        return strategy
