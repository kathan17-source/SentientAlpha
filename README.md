# SentientAlpha

**Quantitative research, multi-agent portfolio analysis, risk governance, and simulation-only paper trading.**

SentientAlpha is a personal engineering portfolio project built around point-in-time financial data, machine-learning research, backtesting, strategy discovery, evidence-backed multi-agent analysis, portfolio optimization, independent risk controls, and a Next.js research dashboard.

## Technical highlights

- **Quant research:** Versioned market data, feature engineering, walk-forward evaluation, automated strategy discovery, and portfolio optimization.
- **ML and NLP:** Financial sentiment processing with FinBERT, versioned forecasts, calibration, and reproducibility checks.
- **Decision engineering:** Structured agent evidence, investment committee aggregation, and independently enforced portfolio risk vetoes.
- **Simulation:** Transactional simulated orders and fills, persistent paper-trading sessions, and restart recovery.
- **Full stack:** Python, FastAPI, SQLAlchemy, React, Next.js, and TypeScript.

## Research results and limitations

This is **research/simulation software**, not a live trading system. No real-money order execution is implemented. In the limited retrospective evaluations reported during development, robust investment alpha was **not established**. Execution, historical coverage, and tail-risk estimates have documented limitations.

## Verification status

The final local verification report recorded 606 backend tests on Python 3.12, 605 on Python 3.14 (with an intentional optional FinBERT test skip), 11 subtests on each version, 59 frontend tests, and 38 demo HTTP checks. Native PostgreSQL, Docker runtime, remote CI, and current browser/accessibility execution remained unverified at that time. These are reported results, not claims of independently audited production readiness.

## Source and reproducibility

**Publication staging:** The project source will be added to this repository only after clearing ownership, third-party redistribution rights, and the separate public-file manifest. Do not upload provider datasets, model caches, held-for-review materials, private credentials, or unreviewed Git history.

A future public release should include safe source code, tests, database migrations, reproducible offline fixtures, architecture documentation, and a demo guide. Document any excluded materials and required local dependencies.

## Rights

Copyright (c) 2026 Kathan Patel. **All rights reserved.** No open-source license is granted for the original materials covered by [LICENSE](LICENSE). Third-party components retain their own applicable terms.
