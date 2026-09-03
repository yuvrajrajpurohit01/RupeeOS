# Contributing to RupeeOS

Thanks for improving RupeeOS. Changes involving payments or autonomous behavior must preserve the central safety contract: agents recommend, policy authorizes, and every executed action is auditable.

## Development workflow

1. Create a focused branch from `main`.
2. Keep secrets out of commits; use the provided `.env.example` files.
3. Add or update tests for every state transition, policy rule, webhook path, or agent capability.
4. Run the backend and frontend checks before opening a pull request.
5. Explain the user-visible behavior and safety impact in the PR template.

## Required checks

```bash
cd backend
python -m pytest -q
python -m compileall -q .

cd ../frontend
npm ci
npm run lint
npm run build
```

## Agent changes

An agent PR should document its input, structured output, confidence semantics, allowed actions, failure mode, and policy boundary. A specialist must never call a payment provider directly. Provider calls belong behind explicit supervisor permission and deterministic policy approval.

## State-machine changes

Update all of the following together:

- `backend/models/money_state.py`
- `VALID_TRANSITIONS` in `backend/services/orchestrator.py`
- frontend `MoneyState` types and status mapping
- architecture documentation
- regression tests

## Commit and PR style

Use clear imperative commit subjects, such as `Add durable recovery workflow trace`. Keep refactors separate from behavior changes when practical.
