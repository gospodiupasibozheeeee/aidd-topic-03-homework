from .client import (
    MarketDataClient,
    MarketDataError,
    quotation_time,
    quotation_to_decimal,
)


def get_last_data(share):
    with MarketDataClient() as client:
        prices = client.last_prices([share.figi])
    for quote in prices:
        if isinstance(quote, dict) and quote.get("figi") == share.figi:
            try:
                return quotation_to_decimal(quote["price"]), quotation_time(
                    quote["time"]
                )
            except KeyError as exc:
                raise MarketDataError("Incomplete quote") from exc
    raise MarketDataError("No price returned for instrument")
