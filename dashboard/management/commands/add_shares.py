from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError

from dashboard.models import Share
from dashboard.services.client import MarketDataClient, MarketDataError


class Command(BaseCommand):
    help = "Import or update the share directory from T-Invest"

    def handle(self, *args, **options):
        try:
            with MarketDataClient() as client:
                instruments = client.shares()
        except MarketDataError as exc:
            raise CommandError(str(exc)) from exc
        created = updated = 0
        for instrument in instruments:
            try:
                defaults = {
                    field: instrument[field]
                    for field in ("name", "isin", "ticker", "currency", "uid")
                }
                _, is_new = Share.objects.update_or_create(
                    figi=instrument["figi"], defaults=defaults
                )
            except (KeyError, TypeError, IntegrityError) as exc:
                raise CommandError(
                    "Invalid or conflicting instrument in market response"
                ) from exc
            created += is_new
            updated += not is_new
        self.stdout.write(self.style.SUCCESS(f"Created: {created}; updated: {updated}"))
