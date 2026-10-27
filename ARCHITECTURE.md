# Architecture

See the [implemented component architecture](docs/ARCHITECTURE.md), [frontend boundaries](docs/FRONTEND_ARCHITECTURE.md), [paper transaction model](docs/PAPER_TRADING.md), [risk gates](docs/RISK_MANAGEMENT.md) and [integration/failure matrix](docs/M12_INTEGRATION_MATRIX.md). The README diagram shows the actual ownership chain.

M12 adds a bounded local HTTP boundary, a bounded BFF stream reader, an after-commit fault observation point, corrected paper freshness handling and frontend container configuration. It adds no financial model, agent, strategy, ledger or executor. Schema remains 0012. The paper event's source-build hash intentionally rejects replay under changed backend source; retain the original release and migration-compatible database for historical replay. Rebuild a fresh deterministic demo for a changed backend.
