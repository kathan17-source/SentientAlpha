"""Offline core tests, runnable with Python's standard library alone."""

import io
import json
import unittest
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from urllib.error import HTTPError, URLError

from sentientalpha.config import Settings
from sentientalpha.data.alphavantage import AlphaVantageProvider
from sentientalpha.data.contracts import PriceBar, ProviderError, ticker_symbol, validate_range
from sentientalpha.data.synthetic import SyntheticProvider

START = date(2024, 1, 2)
END = date(2024, 1, 5)
OBSERVED = datetime(2024, 2, 1, tzinfo=UTC)


def bar() -> PriceBar:
    return PriceBar(
        ticker="AAPL",
        session_date=START,
        open=Decimal("100"),
        high=Decimal("110"),
        low=Decimal("90"),
        close=Decimal("105"),
        volume=100,
        available_at=OBSERVED,
        provider="alphavantage",
        is_synthetic=False,
        availability_kind="observed",
    )


def payload() -> dict:
    return {
        "Meta Data": {"2. Symbol": "AAPL", "5. Time Zone": "US/Eastern"},
        "Time Series (Daily)": {
            day: {
                "1. open": "100",
                "2. high": "110",
                "3. low": "90",
                "4. close": "105",
                "5. volume": "100",
            }
            for day in ("2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05")
        },
    }


class ContractTests(unittest.TestCase):
    def test_valid_bar_and_precision(self):
        self.assertEqual(bar().close, Decimal("105.00000000"))

    def test_invalid_prices(self):
        for value in ("NaN", "Infinity", "-1", "0", "1e12", "1e-20", "abc"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                replace(bar(), close=value)

    def test_ohlc_ordering(self):
        with self.assertRaises(ValueError):
            replace(bar(), high=Decimal("99"))

    def test_volume_is_integral_and_nonnegative(self):
        for value in (-1, 1.5, True, 2**63):
            with self.subTest(value=value), self.assertRaises(ValueError):
                replace(bar(), volume=value)

    def test_naive_availability_rejected(self):
        with self.assertRaises(ValueError):
            replace(bar(), available_at=datetime(2024, 1, 2))

    def test_availability_before_session_rejected(self):
        with self.assertRaises(ValueError):
            replace(bar(), available_at=datetime(2023, 1, 1, tzinfo=UTC))

    def test_synthetic_provenance_consistent(self):
        with self.assertRaises(ValueError):
            replace(bar(), is_synthetic=True)

    def test_ticker_validation(self):
        self.assertEqual(ticker_symbol(" brk.b "), "BRK.B")
        for value in ("../etc", "", "AAPL; DROP", "A" * 13):
            with self.assertRaises(ValueError):
                ticker_symbol(value)

    def test_checksum_ignores_acquisition_but_detects_revision(self):
        self.assertEqual(
            bar().checksum, replace(bar(), available_at=OBSERVED + timedelta(days=1)).checksum
        )
        self.assertNotEqual(bar().checksum, replace(bar(), close=Decimal("106")).checksum)

    def test_date_range_validation(self):
        for start, end in ((END, START), (date(1999, 1, 1), END), (START, date(2055, 1, 1))):
            with self.assertRaises(ValueError):
                validate_range(start, end)

    def test_real_trading_cannot_be_enabled(self):
        with self.assertRaises(ValueError):
            Settings(mode="live")

    def test_settings_repr_hides_secrets(self):
        value = repr(Settings(database_url="sqlite:///secret.db", alpha_vantage_api_key="SECRET"))
        self.assertNotIn("SECRET", value)
        self.assertNotIn("secret.db", value)


class SyntheticTests(unittest.TestCase):
    def test_repeatable(self):
        self.assertEqual(
            SyntheticProvider().fetch("AAPL", START, END),
            SyntheticProvider().fetch("AAPL", START, END),
        )

    def test_seed_changes_data(self):
        self.assertNotEqual(
            SyntheticProvider(1).fetch("AAPL", START, END),
            SyntheticProvider(2).fetch("AAPL", START, END),
        )

    def test_overlapping_ranges_are_identical(self):
        full = SyntheticProvider().fetch("AAPL", START, END)
        self.assertEqual(full[1:], SyntheticProvider().fetch("AAPL", date(2024, 1, 3), END))

    def test_future_range_does_not_change_past(self):
        past = SyntheticProvider().fetch("AAPL", START, END)
        longer = SyntheticProvider().fetch("AAPL", START, date(2024, 6, 1))
        self.assertEqual(past, longer[: len(past)])

    def test_weekends_and_provenance(self):
        rows = SyntheticProvider().fetch("AAPL", START, date(2024, 1, 7))
        self.assertEqual(len(rows), 4)
        self.assertTrue(all(r.is_synthetic and r.availability_kind == "modeled" for r in rows))
        self.assertTrue(all(r.available_at.date() > r.session_date for r in rows))


class ProviderTests(unittest.TestCase):
    def test_parse_raw_prices(self):
        rows = AlphaVantageProvider.parse(payload(), "AAPL", START, END, OBSERVED)
        self.assertEqual(len(rows), 4)
        self.assertIsNone(rows[0].adjusted_close)
        self.assertFalse(rows[0].is_synthetic)
        self.assertEqual(rows[0].available_at, OBSERVED)

    def test_partial_coverage_rejected(self):
        with self.assertRaises(ProviderError) as caught:
            AlphaVantageProvider.parse(payload(), "AAPL", date(2018, 1, 1), END, OBSERVED)
        self.assertEqual(caught.exception.code, "insufficient_coverage")

    def test_quota_errors_redacted(self):
        with self.assertRaises(ProviderError) as caught:
            AlphaVantageProvider.parse({"Information": "SECRET"}, "AAPL", START, END, OBSERVED)
        self.assertNotIn("SECRET", str(caught.exception))

    def test_symbol_mismatch(self):
        with self.assertRaises(ProviderError) as caught:
            AlphaVantageProvider.parse(payload(), "MSFT", START, END, OBSERVED)
        self.assertEqual(caught.exception.code, "symbol_mismatch")

    def test_invalid_numeric_payload(self):
        invalid = payload()
        invalid["Time Series (Daily)"]["2024-01-02"]["4. close"] = "NaN"
        with self.assertRaises(ProviderError):
            AlphaVantageProvider.parse(invalid, "AAPL", START, END, OBSERVED)

    def test_http_fetch_uses_timeout_and_raw_compact(self):
        def opener(request, timeout):
            self.assertEqual(timeout, 20)
            self.assertIn("function=TIME_SERIES_DAILY&", request.full_url)
            self.assertIn("outputsize=compact", request.full_url)
            return io.BytesIO(json.dumps(payload()).encode())

        rows = AlphaVantageProvider("key", opener=opener, clock=lambda: OBSERVED).fetch(
            "AAPL", START, END
        )
        self.assertEqual(len(rows), 4)

    def test_transient_retries_bounded_and_redacted(self):
        attempts = []
        sleeps = []

        def failing(request, timeout):
            attempts.append(1)
            raise URLError("SECRET URL")

        with self.assertRaises(ProviderError) as caught:
            AlphaVantageProvider("SECRET", opener=failing, sleeper=sleeps.append).fetch(
                "AAPL", START, END
            )
        self.assertEqual(len(attempts), 3)
        self.assertEqual(sleeps, [1.0, 2.0])
        self.assertNotIn("SECRET", str(caught.exception))

    def test_permanent_http_error_not_retried(self):
        attempts = []

        def failing(request, timeout):
            attempts.append(1)
            raise HTTPError("SECRET", 403, "SECRET", {}, None)

        with self.assertRaises(ProviderError):
            AlphaVantageProvider("key", opener=failing).fetch("AAPL", START, END)
        self.assertEqual(len(attempts), 1)

    def test_missing_key_rejected(self):
        with self.assertRaises(ProviderError):
            AlphaVantageProvider("")

    def test_bad_json_redacted(self):
        with self.assertRaises(ProviderError) as caught:
            AlphaVantageProvider("key", opener=lambda *a, **kw: io.BytesIO(b"SECRET")).fetch(
                "AAPL", START, END
            )
        self.assertEqual(caught.exception.code, "invalid_json")


if __name__ == "__main__":
    unittest.main()
