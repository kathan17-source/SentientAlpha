# M10 API integration additions

Existing M1–M9 contracts remain authoritative in [OpenAPI](openapi.json). No schema migration or quantitative engine change.

## Read-only discovery

`GET /api/research/catalog?kind=backtest&limit=20&offset=0`: kinds backtest, optimization, ml, strategy, committee, features, sentiment. Limit1–100; offset0–100000. Returns `items`, `next_offset`, `limit`, `offset`. Public item: id, kind, status, created_at, label, allowlisted configuration and related links. Model artifacts/raw source payloads are excluded from SQL selection and output. Results are saved experiments, not a live job queue.

`GET /api/research/coverage?limit=20&offset=0`: limit1–200. Groups retained observations by asset/provider with earliest/latest dates, count, availability/ingestion and synthetic flag. A retained range does not establish session completeness or live quotes. Empty DB returns empty items. Invalid bounds/kinds fail validation.

## Local frontend proxy

The browser uses `/api/backend/...`; the server forwards allowed requests to fixed `API_BASE_URL`. POST requires an explicit `DASHBOARD_ORIGINS` match. Research creation/replay/stress are allowed only on listed paths; broker/market writes are absent. Requests are bounded, cancelable and errors sanitized. This is loopback single-user integration, not authentication for public hosting.

See [frontend architecture](FRONTEND_ARCHITECTURE.md) and M10 report (historical evidence archived locally) for financial units, timing, request review and validation scope.
