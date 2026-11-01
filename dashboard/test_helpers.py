from .models import Share


def make_share(number=1, **overrides):
    return Share.objects.create(
        **{
            "figi": f"FIGI{number}",
            "isin": f"ISIN{number}",
            "name": f"Company {number}",
            "ticker": f"TEST{number}",
            "currency": "rub",
            "uid": f"uid-{number}",
            **overrides,
        }
    )
