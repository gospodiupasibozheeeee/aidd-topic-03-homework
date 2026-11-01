from __future__ import annotations

import logging

from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError

from dashboard.models import Share, generate_uid
from dashboard.services.tinkoff import MarketDataError, tinkoff_client

logger = logging.getLogger("dashboard")


class Command(BaseCommand):
    help = "Import the Tinkoff share catalogue into the database"

    def handle(self, *args, **options):
        created = 0
        updated = 0
        skipped = 0

        try:
            with tinkoff_client() as client:
                response = client.instruments.shares()
                instruments = getattr(response, "instruments", []) or []

                for instrument in instruments:
                    figi = getattr(instrument, "figi", None)
                    if not figi:
                        skipped += 1
                        continue

                    defaults = {
                        "isin": getattr(instrument, "isin", "") or "",
                        "name": getattr(instrument, "name", "") or "",
                        "ticker": getattr(instrument, "ticker", "") or "",
                        "currency": str(getattr(instrument, "currency", "") or ""),
                        "uid": getattr(instrument, "uid", "") or generate_uid(),
                    }

                    try:
                        _, was_created = Share.objects.update_or_create(
                            figi=figi,
                            defaults=defaults,
                        )
                    except IntegrityError as exc:
                        skipped += 1
                        logger.warning("Skipping %s: %s", figi, exc)
                        continue

                    if was_created:
                        created += 1
                    else:
                        updated += 1
        except MarketDataError as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(
            self.style.SUCCESS(
                f"Shares imported: created={created}, updated={updated}, "
                f"skipped={skipped}"
            )
        )
