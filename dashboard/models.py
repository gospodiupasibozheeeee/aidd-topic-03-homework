from __future__ import annotations

import uuid
from decimal import Decimal

from django.db import models


def generate_uid() -> str:
    """Return a stable unique identifier for manually created shares."""

    return str(uuid.uuid4())


class Share(models.Model):
    """A stock (share) available in the catalogue."""

    figi = models.CharField(max_length=255, unique=True, verbose_name="FIGI")
    isin = models.CharField(max_length=255, verbose_name="ISIN")
    name = models.CharField(
        max_length=255, db_index=True, verbose_name="Наименование компании"
    )
    ticker = models.CharField(max_length=10, unique=True, verbose_name="Тикер")
    currency = models.CharField(max_length=20, verbose_name="Валюта")
    uid = models.CharField(
        max_length=255,
        unique=True,
        blank=True,
        default=generate_uid,
        verbose_name="UID инструмента",
    )
    last_price = models.DecimalField(
        max_digits=20,
        decimal_places=9,
        blank=True,
        null=True,
        verbose_name="Текущая цена",
    )
    is_trend_high = models.BooleanField(
        default=False,
        verbose_name="Растет цена",
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        blank=True,
        null=True,
        verbose_name="Обновлено",
    )

    class Meta:
        verbose_name = "Акция"
        verbose_name_plural = "Акции"
        ordering = ["name"]

    def __str__(self) -> str:
        return f"{self.ticker} — {self.name}"

    @property
    def price_as_decimal(self) -> Decimal | None:
        """Return the price as Decimal regardless of the database backend."""

        if self.last_price is None:
            return None
        return Decimal(str(self.last_price))
