"""Seed the currencies and payment methods every market starts from."""

from django.db import migrations

CURRENCIES = (
    ("BRL", 2, "Brazilian real"),
    ("USD", 2, "US dollar"),
    ("EUR", 2, "Euro"),
    ("MXN", 2, "Mexican peso"),
    ("ARS", 2, "Argentine peso"),
    ("CLP", 0, "Chilean peso"),
    ("COP", 2, "Colombian peso"),
    ("JPY", 0, "Japanese yen"),
    ("GBP", 2, "Pound sterling"),
    ("CAD", 2, "Canadian dollar"),
)

PAYMENT_METHODS = (
    ("card", "credit_card", "Credit card", ""),
    ("card", "debit_card", "Debit card", ""),
    ("instant_transfer", "pix", "Pix", "BR"),
    ("bank_slip", "boleto", "Boleto", "BR"),
    ("wallet", "wallet", "Digital wallet", ""),
    ("store_credit", "gift_card", "Gift card", ""),
)


def seed(apps, schema_editor):
    """Create the reference rows, leaving existing ones untouched."""
    _ = schema_editor
    currency = apps.get_model("commerce", "Currency")
    for code, minor_unit, name in CURRENCIES:
        currency.objects.get_or_create(
            code=code,
            defaults={"minor_unit": minor_unit, "name": name},
        )
    payment_method = apps.get_model("commerce", "PaymentMethod")
    for family, code, name, country in PAYMENT_METHODS:
        payment_method.objects.get_or_create(
            code=code,
            country=country,
            defaults={"family": family, "name": name},
        )


class Migration(migrations.Migration):
    """Reference data, reversible as a no-op."""

    dependencies = (("commerce", "0001_initial"),)

    operations = (migrations.RunPython(seed, migrations.RunPython.noop),)
