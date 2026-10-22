> Historical audit/release record. The owner has now selected All Rights Reserved and authorized a private candidate upload. Current selection and verification supersede earlier pending-decision/upload statements: [publication selection](PUBLICATION_SELECTION.md), [current report](GITHUB_PORTFOLIO_PREPARATION.md). Historical results remain historical.

# SentientAlpha — portfolio presentation

## Concise explanation

A local full-stack quantitative research platform that connects time-safe data and ML experiments to an evidence-backed investment committee, independent risk checks and persistent simulated execution.

## Engineering problem and implemented system

Research results are difficult to trust when data revisions leak into historical decisions, proposed weights look like actual holdings, or a restarted worker applies the same fill twice. SentientAlpha preserves data/version clocks and evidence, separates proposal/risk/execution authority, and restores an authoritative portfolio from durable events.

Implemented subsystems: versioned ingestion; as-of price/news features; optional CPU FinBERT; fitted-on-training-only preprocessing, matured labels and calibration; constrained portfolio optimization; bounded declarative strategy discovery and holdouts; specialized agent evidence and abstentions; independent pre-trade/fill-time/post-fill risk; M4 Decimal accounting and execution; experiment replay; persistent paper sessions; FastAPI and eleven Next.js routes.

Technologies used: Python3.12/3.14, FastAPI, SQLAlchemy/Alembic, SQLite, PostgreSQL dialect/configuration, NumPy/pandas/SciPy/scikit-learn, optional PyTorch/Transformers, Next.js/React/TypeScript, Tailwind/Recharts, pytest/Vitest, Playwright/axe configuration, Docker/Compose and GitHub Actions configuration. PostgreSQL/container/remote CI execution remains blocked here; list those as configured infrastructure, not deployment achievements.

## Three résumé bullet options

- Built a full-stack quantitative research platform with versioned data, time-safe ML evaluation, constrained portfolio optimization and evidence-backed multi-agent orchestration using Python, FastAPI and Next.js/TypeScript.
- Implemented persistent simulated trading with independent pre-trade and fill-time risk gates, Decimal portfolio accounting, idempotent commands and transaction-safe recovery; verified that real process crashes before and after commit do not duplicate economic fills.
- Verified 605 core backend tests plus 11 subtests on Python3.12 and3.14, 59 frontend tests and 38 local full-stack HTTP checks; reproduced an offline demo, reconciled restarted portfolio state and tested an optional NLP security upgrade with real FinBERT inference.

The post-release3.12 run includes the optional model test:606 total, rather than an additional new core test. No benchmark speedup or investment outperformance claim is supported.

## 60-second interview explanation

“I built SentientAlpha to study the engineering behind reproducible quantitative research. It connects versioned market data and time-safe features to ML experiments, strategy discovery and a committee of specialized research agents. The committee proposes an allocation through an optimizer, but an independent risk manager can veto it before execution and again before a simulated fill. Accounting belongs to a single Decimal ledger, and paper sessions persist commands, orders, fills and evidence so a restarted worker can recover safely. I tested actual process crashes on both sides of the commit boundary and checked that retrying causes one economic effect. The interface exposes saved evidence and limitations through FastAPI and Next.js. It is a local research and simulation project, not a production trading system. Its genuine IBM committee experiment underperformed buy-and-hold, so I present the result as evidence of the research process, not profitable alpha.”

## Five-minute technical walkthrough

| Time | Explain and show |
|---|---|
| 0–1 minute | Trace market/news source clocks, revisions and as-of lineage. Explain why later information cannot rewrite earlier evidence. The offline demo is synthetic. |
| 1–2 minutes | Inspect actual M6 experiment windows, training-only transforms, matured labels/calibration, M7 candidates and holdout restrictions. Missing sentiment is unavailable, not neutral. |
| 2–3 minutes | Follow committee evidence/abstentions into optimizer proposal weights. Explain independent target/fill risk authority and the veto session's insufficient tails. Proposed allocations are not holdings. |
| 3–4 minutes | Trace one approved simulated order through next-observed-close execution, costs, Decimal cash/positions, unique receipt and event checkpoint. Show the crash tests and reconcile persisted history. |
| 4–5 minutes | Show API/BFF contracts and dashboard, fresh setup/restart evidence, regression counts and release manifest. State blocked infrastructure/browser verification and the negative IBM result. |

## Research discipline and limits

Purged/embargoed windows, matured targets, separate calibration, locked holdout and time-eligible evidence are engineering controls; they do not prove alpha. Genuine historical macro/fundamental/sentiment coverage is incomplete, tail samples are small, the universe may have survivorship bias, and execution is approximate. Genuine IBM committee return −8.70% versus buy-and-hold −4.69%; risk controls reduced reported exposure/losses. Long-term forward performance is unestablished.

See [post-release evidence](POST_RELEASE_VERIFICATION.md), [demo](DEMO.md) and [licensing review](LICENSE_REVIEW.md). No production readiness, accessibility certification, live-money routing, profitable strategy or remote CI success is claimed.
