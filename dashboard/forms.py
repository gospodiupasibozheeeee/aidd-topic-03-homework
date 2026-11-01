from __future__ import annotations

from django import forms

from .models import Share


class ShareModelForm(forms.ModelForm):
    """Form for manual creation/editing of a share.

    ``uid`` is generated automatically by the model and ``updated_at`` is
    managed by Django, so neither field is exposed to the user.
    """

    class Meta:
        model = Share
        fields = (
            "figi",
            "isin",
            "name",
            "ticker",
            "currency",
            "last_price",
            "is_trend_high",
        )
        widgets = {
            "last_price": forms.NumberInput(
                attrs={"step": "0.000000001", "min": "0", "placeholder": "0.00"}
            ),
        }
        help_texts = {
            "figi": "Идентификатор FIGI из Tinkoff Invest API.",
        }

    def clean_figi(self):
        return (self.cleaned_data.get("figi") or "").strip()

    def clean_ticker(self):
        return (self.cleaned_data.get("ticker") or "").strip().upper()

    def clean_last_price(self):
        value = self.cleaned_data.get("last_price")
        if value is not None and value < 0:
            raise forms.ValidationError("Цена не может быть отрицательной.")
        return value
