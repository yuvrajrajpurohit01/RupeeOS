# API Reference

Interactive OpenAPI documentation is served at `/docs`; the machine-readable schema is at `/openapi.json`.

## Core resources

| Method | Route | Purpose |
| --- | --- | --- |
| `POST` | `/transactions` | Create a persistent money object |
| `GET` | `/transactions` | List and optionally filter transactions |
| `GET` | `/transactions/{money_id}` | Get one transaction and its state history |
| `POST` | `/transactions/{money_id}/checkout` | Finalize cart and enter checkout state |
| `POST` | `/transactions/{money_id}/risk-analyze` | Compatibility endpoint for direct risk execution |
| `POST` | `/transactions/{money_id}/pay` | Create a policy-gated Razorpay Test order |
| `POST` | `/transactions/{money_id}/payment/verify` | Verify Standard Checkout signature |
| `POST` | `/transactions/{money_id}/recover` | Compatibility endpoint for direct recovery execution |

## Agentic runtime

| Method | Route | Purpose |
| --- | --- | --- |
| `GET` | `/agentic/agents` | Inspect agent roles, tools, and guardrails |
| `POST` | `/agentic/runs` | Start a durable supervisor run |
| `GET` | `/agentic/runs` | List runs; filter by `money_id` |
| `GET` | `/agentic/runs/{run_id}` | Inspect a complete trace |
| `POST` | `/agentic/runs/{run_id}/resume` | Resume after approval/evidence or change action permission |

Start request:

```json
{
  "money_id": "txn_123",
  "goal": "ASSESS_AND_ROUTE_PAYMENT",
  "max_steps": 8,
  "execute_external_actions": false
}
```

`execute_external_actions` is deliberately false by default. Enabling it permits the supervisor to prepare a Razorpay Test Mode order only after policy approval; it does not let the agent fabricate payment success.

## Human review

| Method | Route | Purpose |
| --- | --- | --- |
| `GET` | `/manual-reviews?status=PENDING` | List review work |
| `POST` | `/manual-reviews/{review_id}/approve` | Approve a gated action |
| `POST` | `/manual-reviews/{review_id}/reject` | Reject a gated action |

## Finance and evidence

| Method | Route | Purpose |
| --- | --- | --- |
| `POST` | `/reconciliation/run` | Reconcile settlement records |
| `GET` | `/reconciliation/batch?batch_id=...` | Read a stored batch |
| `POST` | `/webhooks/razorpay` | Receive signed Razorpay webhooks |
| `GET` | `/audit` | Read audit entries |
| `GET` | `/audit/verify` | Recompute one or all audit chains |
| `GET` | `/policy-decisions` | Read policy decisions |
| `GET` | `/agent-runs` | Read specialist telemetry |

## Operations

| Method | Route | Purpose |
| --- | --- | --- |
| `GET` | `/health/live` | Process liveness |
| `GET` | `/health/ready` | Database readiness and provider configuration state |
| `GET` | `/system/status` | Circuit breaker and runtime status |
| `GET` | `/ai/status` | AI provider, model, configuration and authority status; never returns the API key |
| `GET` | `/command-center/metrics` | Aggregated operational metrics |
| `POST` | `/evaluation/recovery-batch` | Seeded synthetic evaluation only |

Demo-only failure-spike controls are disabled when `RUPEEOS_DEMO_MODE=false`.

## Errors

- `400`: invalid signature or malformed signed payload.
- `404`: unknown transaction, workflow, review, or reconciliation batch.
- `409`: invalid Money State Graph transition or unmet policy gate.
- `422`: Pydantic request validation failure.
- `503`: database/payment-provider configuration or availability failure.
