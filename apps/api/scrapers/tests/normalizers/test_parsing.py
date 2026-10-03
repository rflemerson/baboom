"""Prices are parsed to exact decimals, in the formats stores publish."""

from __future__ import annotations

from decimal import Decimal

from django.test import SimpleTestCase

from scrapers.normalizers.parsing import parse_positive_price


class ParsePositivePriceTests(SimpleTestCase):
    """No price passes through binary floating point."""

    def test_returns_a_decimal(self) -> None:
        """A JSON float becomes the decimal it was written as."""
        price = parse_positive_price(149.9)

        assert isinstance(price, Decimal)
        assert price == Decimal("149.9")

    def test_integer_cents(self) -> None:
        """Shopify .js prices are integer cents."""
        assert parse_positive_price(14989, cents_for_int=True) == Decimal("149.89")

    def test_digit_string_cents(self) -> None:
        """A digit string in cents keeps every cent."""
        assert parse_positive_price("1390", cents_for_digit_string=True) == Decimal(
            "13.90",
        )

    def test_brazilian_format_with_thousands(self) -> None:
        """R$ 1.234,56 is one thousand two hundred, not one."""
        assert parse_positive_price("R$ 1.234,56") == Decimal("1234.56")

    def test_brazilian_format_without_thousands(self) -> None:
        """R$310,56 is three hundred and ten."""
        assert parse_positive_price("R$310,56") == Decimal("310.56")

    def test_dot_decimal_format(self) -> None:
        """A plain dotted decimal string."""
        assert parse_positive_price("1234.5") == Decimal("1234.5")

    def test_dot_thousands_with_comma_decimal_is_not_confused(self) -> None:
        """1,234.56 in the US format."""
        assert parse_positive_price("1,234.56") == Decimal("1234.56")

    def test_zero_and_negative_are_absent(self) -> None:
        """Zero is not a price."""
        assert parse_positive_price(0) is None
        assert parse_positive_price("-3") is None
        assert parse_positive_price("") is None
        assert parse_positive_price(None) is None
