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
