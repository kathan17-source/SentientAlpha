"""Official raw daily compact API. No inference of historical publication times."""

import json
import time
from collections.abc import Callable
from contextlib import AbstractContextManager
from datetime import UTC, date, datetime
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from sentientalpha.data.calendar import session_close, sessions_in_range
from sentientalpha.data.contracts import PriceBar, ProviderError, ticker_symbol, utc, validate_range


class ResponseReader(Protocol):
    def read(self, size: int = -1) -> bytes: ...


ResponseOpener = Callable[..., AbstractContextManager[ResponseReader]]


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON field")
        result[key] = value
    return result


class AlphaVantageProvider:
    name = "alphavantage"
    parameters = {"function": "TIME_SERIES_DAILY", "outputsize": "compact"}

    def __init__(
        self,
        api_key: str,
        *,
        opener: ResponseOpener = urlopen,
        sleeper: Callable[[float], None] = time.sleep,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        if not isinstance(api_key, str) or not api_key.strip():
            raise ProviderError("missing_key", "ALPHA_VANTAGE_API_KEY is required")
        self._api_key = api_key
        self._opener = opener
        self._sleep = sleeper
        self._clock = clock

    def fetch(self, ticker: str, start: date, end: date) -> list[PriceBar]:
        validate_range(start, end)
        ticker = ticker_symbol(ticker)
        if "." in ticker and len(ticker.rsplit(".", 1)[1]) != 1:
            raise ProviderError("unsupported_market", "Foreign exchange suffixes are unsupported")
        parameters = {
            "function": "TIME_SERIES_DAILY",
            "symbol": ticker,
            "apikey": self._api_key,
        }
        # Public IBM demo accepts the exact documented URL. Compact is the API default.
        if self._api_key != "demo":
            parameters["outputsize"] = "compact"
        params = urlencode(parameters)
        request = Request(
            "https://www.alphavantage.co/query?" + params,
            headers={"User-Agent": "SentientAlpha/0.1 research"},
        )
        payload = None
        for attempt in range(3):
            try:
                with self._opener(request, timeout=20) as response:
                    raw = response.read(5_000_001)
                if len(raw) > 5_000_000:
                    raise ProviderError(
                        "oversized_response", "Provider response exceeds size limit"
                    )
                payload = json.loads(raw, object_pairs_hook=_unique_object)
                break
            except HTTPError as exc:
                exc.close()
                if exc.code not in {429, 500, 502, 503, 504} or attempt == 2:
                    raise ProviderError("http_error", "Market provider HTTP failure") from None
            except (URLError, TimeoutError, OSError):
                if attempt == 2:
                    raise ProviderError("network_error", "Market provider unavailable") from None
            except (ValueError, UnicodeError):
                raise ProviderError(
                    "invalid_json", "Market provider returned invalid JSON"
                ) from None
            self._sleep(float(2**attempt))
        return self.parse(payload, ticker, start, end, self._clock())

    @staticmethod
    def parse(
        payload: object,
        ticker: str,
        start: date,
        end: date,
        observed_at: datetime,
    ) -> list[PriceBar]:
        try:
            validate_range(start, end)
            ticker = ticker_symbol(ticker)
            observed_at = utc(observed_at)
        except ValueError:
            raise ProviderError(
                "invalid_request", "Invalid provider request bounds or timestamp"
            ) from None
        if not isinstance(payload, dict):
            raise ProviderError("invalid_payload", "Expected a provider object")
        if "Note" in payload or "Information" in payload:
            raise ProviderError(
                "provider_limit", "Provider quota or entitlement prevents this request"
            )
        if "Error Message" in payload:
            raise ProviderError("provider_rejected", "Provider rejected the requested symbol")
        series = payload.get("Time Series (Daily)")
        if not isinstance(series, dict) or not series:
            raise ProviderError("missing_series", "Provider returned no daily prices")
        metadata = payload.get("Meta Data", {})
        symbol = metadata.get("2. Symbol") if isinstance(metadata, dict) else None
        if not isinstance(symbol, str) or symbol.upper() != ticker:
            raise ProviderError("symbol_mismatch", "Provider symbol does not match request")
        timezone = metadata.get("5. Time Zone")
        if not isinstance(timezone, str) or timezone not in {"US/Eastern", "America/New_York"}:
            raise ProviderError("unsupported_market", "Only US-session USD assets are supported")
        try:
            expected = sessions_in_range("XNYS", start, end)
            if not expected:
                return []
            dates = sorted(date.fromisoformat(day) for day in series)
            # Strict coverage check: even holiday-only boundary gaps are surfaced, never hidden.
            if expected[0] < dates[0] or expected[-1] > dates[-1]:
                raise ProviderError(
                    "insufficient_coverage",
                    "Requested bounds exceed compact coverage; narrow dates or change provider",
                )
            rows = []
            for day in dates:
                if not start <= day <= end:
                    continue
                row = series[day.isoformat()]
                rows.append(
                    PriceBar(
                        ticker=ticker,
                        session_date=day,
                        open=row["1. open"],
                        high=row["2. high"],
                        low=row["3. low"],
                        close=row["4. close"],
                        volume=int(str(row["5. volume"])),
                        available_at=observed_at,
                        provider="alphavantage",
                        is_synthetic=False,
                        availability_kind="observed",
                        session_close_at=session_close("XNYS", day),
                        calendar="XNYS",
                        adjustment_status="not_supplied",
                    )
                )
            return rows
        except (ValueError, KeyError, TypeError, AttributeError, OverflowError):
            raise ProviderError("invalid_prices", "Provider prices failed validation") from None
