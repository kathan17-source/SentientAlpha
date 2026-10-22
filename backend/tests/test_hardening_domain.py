"""Regression coverage for malformed transport, price boundaries and market calendars."""

import io
import json
from dataclasses import replace
from datetime import UTC, date, datetime
from decimal import Decimal
from urllib.error import HTTPError

import pytest
from sentientalpha.data.alphavantage import AlphaVantageProvider
from sentientalpha.data.calendar import session_close, sessions_in_range
from sentientalpha.data.contracts import ProviderError, price
from sentientalpha.data.quality import assess_batch
from sentientalpha.data.synthetic import SyntheticProvider
from test_domain import END, OBSERVED, START, bar, payload


@pytest.mark.parametrize("value", ["999999999999.999999999", "1e-9", "NaN", "Infinity"])
def test_rounded_price_range_is_enforced(value):
    with pytest.raises(ValueError):
        price(value)


@pytest.mark.parametrize(
    "field,value",
    [
        ("is_synthetic", 1),
        ("currency", "CAD"),
        ("calendar", "invented"),
        ("session_date", datetime(2024, 1, 2, tzinfo=UTC)),
        ("adjustment_status", "supplied"),
        ("session_close_at", datetime(2024, 2, 1, tzinfo=UTC)),
    ],
)
def test_inconsistent_metadata_rejected(field, value):
    with pytest.raises(ValueError):
        replace(bar(), **{field: value})


@pytest.mark.parametrize("metadata", [{"2. Symbol": 123}, None, ["AAPL"]])
def test_malformed_metadata_has_sanitized_provider_error(metadata):
    data = payload()
    data["Meta Data"] = metadata
    with pytest.raises(ProviderError, match="symbol"):
        AlphaVantageProvider.parse(data, "AAPL", START, END, OBSERVED)


@pytest.mark.parametrize("timezone", ["Europe/London", "UTC", None])
def test_non_us_source_not_mislabeled_usd(timezone):
    data = payload()
    data["Meta Data"]["5. Time Zone"] = timezone
    with pytest.raises(ProviderError) as caught:
        AlphaVantageProvider.parse(data, "AAPL", START, END, OBSERVED)
    assert caught.value.code == "unsupported_market"


def test_provider_duplicate_json_fields_rejected():
    raw = b'{"Time Series (Daily)":{},"Time Series (Daily)":{}}'
    provider = AlphaVantageProvider("dummy", opener=lambda *a, **kw: io.BytesIO(raw))
    with pytest.raises(ProviderError) as caught:
        provider.fetch("AAPL", START, END)
    assert caught.value.code == "invalid_json"


def test_public_demo_request_uses_documented_canonical_shape():
    data = payload()
    data["Meta Data"]["2. Symbol"] = "IBM"

    def opener(request, timeout):
        assert request.full_url == (
            "https://www.alphavantage.co/query?function=TIME_SERIES_DAILY&symbol=IBM&apikey=demo"
        )
        return io.BytesIO(json.dumps(data).encode())

    assert (
        len(
            AlphaVantageProvider("demo", opener=opener, clock=lambda: OBSERVED).fetch(
                "IBM", START, END
            )
        )
        == 4
    )


def test_http_429_retries_then_succeeds():
    attempts = 0
    delays = []

    def opener(request, timeout):
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise HTTPError("redacted", 429, "rate limited", {}, None)
        return io.BytesIO(json.dumps(payload()).encode())

    provider = AlphaVantageProvider(
        "dummy", opener=opener, sleeper=delays.append, clock=lambda: OBSERVED
    )
    assert len(provider.fetch("AAPL", START, END)) == 4
    assert attempts == 3 and delays == [1.0, 2.0]


def test_timeout_retries_exhausted():
    attempts = []

    def opener(request, timeout):
        attempts.append(1)
        raise TimeoutError("private transport details")

    with pytest.raises(ProviderError) as caught:
        AlphaVantageProvider("dummy", opener=opener, sleeper=lambda _: None).fetch(
            "AAPL", START, END
        )
    assert len(attempts) == 3 and caught.value.code == "network_error"
    assert "private" not in str(caught.value)


def test_missing_trading_session_recorded_not_filled():
    rows = AlphaVantageProvider.parse(payload(), "AAPL", START, END, OBSERVED)
    rows.pop(1)
    report, _ = assess_batch(rows, START, END)
    assert report["missing_sessions"] == ["2024-01-03"]
    assert len(rows) == 3 and report["transformations"] == []


def test_price_discontinuity_flagged_without_repair():
    rows = SyntheticProvider().fetch("AAPL", START, END)
    rows[-1] = replace(
        rows[-1], open=Decimal("50"), high=Decimal("51"), low=Decimal("49"), close=Decimal("50")
    )
    report, flags = assess_batch(rows, START, END)
    assert report["state"] == "warnings"
    assert flags[END] == ["price_discontinuity"]
    assert rows[-1].close == Decimal("50") and report["transformations"] == []


def test_nyse_holidays_early_closes_and_dst():
    assert sessions_in_range("XNYS", date(2024, 7, 4), date(2024, 7, 4)) == []
    assert session_close("XNYS", date(2024, 7, 3)).hour == 17
    assert session_close("XNYS", date(2024, 1, 5)).hour == 21
    assert session_close("XNYS", date(2024, 7, 5)).hour == 20


def test_non_session_provider_row_rejected():
    rows = SyntheticProvider().fetch("AAPL", date(2024, 7, 3), date(2024, 7, 5))
    rows = [replace(row, calendar="XNYS") for row in rows]
    with pytest.raises(ProviderError, match="nontrading"):
        assess_batch(rows, date(2024, 7, 3), date(2024, 7, 5))


def test_holiday_only_query_is_empty_without_inventing_bars():
    assert (
        AlphaVantageProvider.parse(payload(), "AAPL", date(2024, 1, 6), date(2024, 1, 7), OBSERVED)
        == []
    )


def test_unhashable_timezone_is_a_provider_error():
    data = payload()
    data["Meta Data"]["5. Time Zone"] = ["US/Eastern"]
    with pytest.raises(ProviderError) as caught:
        AlphaVantageProvider.parse(data, "AAPL", START, END, OBSERVED)
    assert caught.value.code == "unsupported_market"


def test_foreign_exchange_suffix_rejected_before_transport():
    def no_network(*args, **kwargs):
        pytest.fail("Foreign exchange requests must be rejected before transport")

    with pytest.raises(ProviderError) as caught:
        AlphaVantageProvider("dummy", opener=no_network).fetch("SHOP.TRT", START, END)
    assert caught.value.code == "unsupported_market"
