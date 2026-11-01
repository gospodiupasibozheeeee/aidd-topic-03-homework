from django.core.management.base import BaseCommand

from dashboard.models import Share
from dashboard.services.client import TinkoffClient


class Command(BaseCommand):
    help = "Загрузка справочника акций из Tinkoff Invest API в базу данных"

    def handle(self, *args, **options):
        client = TinkoffClient()
        if not client.token:
            self.stdout.write(
                self.style.WARNING(
                    "TINKOFF_TOKEN не задан. Укажите токен в .env для загрузки акций из реального API."
                )
            )
            return

        instruments = client.get_shares()
        if not instruments:
            self.stdout.write(self.style.WARNING("Не получено инструментов от Tinkoff API."))
            return

        created_count = 0
        updated_count = 0

        for item in instruments:
            figi = item.get("figi")
            if not figi:
                continue

            ticker = item.get("ticker", "")
            name = item.get("name", "")
            isin = item.get("isin", "")
            currency = item.get("currency", "")
            uid = item.get("uid", "")

            _, created = Share.objects.update_or_create(
                figi=figi,
                defaults={
                    "name": name,
                    "isin": isin,
                    "ticker": ticker,
                    "currency": currency,
                    "uid": uid or figi,
                },
            )
            if created:
                created_count += 1
            else:
                updated_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Импорт завершен: создано {created_count}, обновлено {updated_count} акций."
            )
        )
