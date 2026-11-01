import uuid
from django import forms

from .models import Share


class ShareModelForm(forms.ModelForm):
    """Форма добавления и редактирования акции"""

    class Meta:
        model = Share
        fields = [
            "name",
            "ticker",
            "figi",
            "isin",
            "currency",
            "uid",
            "last_price",
            "is_trend_high",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "Например, Apple Inc."}),
            "ticker": forms.TextInput(attrs={"placeholder": "AAPL"}),
            "figi": forms.TextInput(attrs={"placeholder": "BBG000B9XRY4"}),
            "isin": forms.TextInput(attrs={"placeholder": "US0378331005"}),
            "currency": forms.TextInput(attrs={"placeholder": "USD"}),
            "uid": forms.TextInput(attrs={"placeholder": "Оставьте пустым для автогенерации"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["uid"].required = False

    def clean_uid(self):
        uid = self.cleaned_data.get("uid")
        if not uid:
            return str(uuid.uuid4())
        return uid


class WatchlistForm(forms.ModelForm):
    """Форма добавления акции в персональный список наблюдения"""

    class Meta:
        from .models import WatchlistItem

        model = WatchlistItem
        fields = ["share", "target_price", "condition"]
        widgets = {
            "share": forms.Select(attrs={"class": "form-control"}),
            "target_price": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.01", "placeholder": "150.00"}
            ),
            "condition": forms.Select(attrs={"class": "form-control"}),
        }

    def clean_target_price(self):
        target = self.cleaned_data.get("target_price")
        if target is not None and target <= 0:
            raise forms.ValidationError("Целевая цена должна быть строго больше 0.")
        return target


class PortfolioTradeForm(forms.Form):
    """Форма виртуальной покупки/продажи акций в портфеле"""

    ACTION_CHOICES = (
        ("BUY", "Купить"),
        ("SELL", "Продать"),
    )
    action = forms.ChoiceField(
        choices=ACTION_CHOICES,
        widget=forms.Select(attrs={"class": "form-control"}),
        label="Действие",
    )
    share = forms.ModelChoiceField(
        queryset=Share.objects.all(),
        widget=forms.Select(attrs={"class": "form-control"}),
        label="Инструмент",
    )
    quantity = forms.IntegerField(
        min_value=1,
        widget=forms.NumberInput(attrs={"class": "form-control", "min": 1, "value": 1}),
        label="Количество акций",
    )


class TradingStrategyForm(forms.ModelForm):
    """Форма создания и настройки инвестиционной стратегии"""

    class Meta:
        from .models import TradingStrategy

        model = TradingStrategy
        fields = [
            "name",
            "share",
            "strategy_type",
            "buy_threshold",
            "sell_threshold",
            "trade_quantity",
            "is_active",
        ]
        widgets = {
            "name": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Например: Buy the dip AAPL"}
            ),
            "share": forms.Select(attrs={"class": "form-control"}),
            "strategy_type": forms.Select(attrs={"class": "form-control"}),
            "buy_threshold": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "step": "0.01",
                    "placeholder": "Порог покупки (цена или %)",
                }
            ),
            "sell_threshold": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "step": "0.01",
                    "placeholder": "Порог продажи (цена или %)",
                }
            ),
            "trade_quantity": forms.NumberInput(
                attrs={"class": "form-control", "min": 1, "value": 1}
            ),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def clean(self):
        cleaned_data = super().clean()
        st_type = cleaned_data.get("strategy_type")
        buy_t = cleaned_data.get("buy_threshold")
        sell_t = cleaned_data.get("sell_threshold")

        if st_type == "THRESHOLD_BUY_SELL" and buy_t and sell_t:
            if buy_t >= sell_t:
                self.add_error(
                    "buy_threshold",
                    "Для пороговой стратегии цена покупки должна быть строго ниже цены продажи.",
                )
        return cleaned_data

