# Changelog

## 4.1.0 - 2026-09-04

- Added optional OpenAI `gpt-5.6-terra` structured reasoning for risk and recovery workflows.
- Added schema-constrained specialist selection, diagnosis, evidence, confidence, and recovery plans.
- Added conservative AI/rules aggregation so model output cannot weaken a safety recommendation.
- Added `/ai/status`, Command Center AI state, safe fallback behavior, configuration and regression tests.

All notable project changes are documented here.

## 4.0.0 — 2026-09-03

### Added

- Durable agentic supervisor with state-driven routing, maximum-step budgets, pause/resume, external-action permission, and persisted structured traces.
- Inspectable manifests for Supervisor, Growth, Risk, Recovery, and Finance agents.
- Agentic workflow API and Command Center runtime views.
- Live Growth Agent API wiring with catalog-backed product/add-on evidence and telemetry.
- Pydantic request validation for core public endpoints.
- Audit-chain verification endpoint and live/readiness probes.
- Docker Compose, production container builds, GitHub Actions, Dependabot, issue templates, PR template, and project documentation.
- Regression coverage for supervisor routing, budget enforcement, audit verification, validation, and health.

### Changed

- Risk and Recovery UI actions now invoke the durable supervisor.
- Frontend dependency lockfile is synchronized with `package.json`.
- UTC timestamps use an explicit Python 3.12-compatible clock helper.
- API version advanced to `4.0.0`.

## 3.0.0 — 2026-08-28

- Connected the Next.js UI to the FastAPI/SQLite backend.
- Added Razorpay Test Mode orders, signature validation, verified webhooks, human approval, circuit breaker, recovery orders, reconciliation, and hash-chained audit entries.
