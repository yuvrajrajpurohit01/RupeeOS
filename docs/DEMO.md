# Buildathon Demo Guide

## Before presenting

- Start FastAPI on port `8000` and Next.js on `3000`.
- Confirm `/health/ready` returns `ready`.
- Confirm Command Center shows `FastAPI connected` and Razorpay configuration is true.
- Start the Cloudflare tunnel and verify the Razorpay webhook URL/secret.
- Keep Swagger `/docs` open as a backup.
- Use Razorpay Test Mode only.

## Five-minute story

### 1. The problem — 30 seconds

“A payment is not one API call. It passes through discovery, risk, checkout, recovery, settlement, and operations. RupeeOS gives every rupee one persistent state and coordinates bounded agents around it.”

### 2. Safe agentic checkout — 75 seconds

1. Open Commerce and choose `RupeePods Pro`.
2. Run Growth Agent and optionally accept the add-on.
3. Create checkout and open Risk.
4. Run the agentic supervisor.
5. Explain that the durable run selected Risk Agent, captured evidence, obtained policy approval, and paused because external actions were not silently enabled.
6. Click Pay with Razorpay and complete Test Mode checkout.

### 3. Human gate — 60 seconds

1. Create `Merchant Creator Kit` (above ₹10,000).
2. Run the supervisor; the policy sends it to `MANUAL_REVIEW`.
3. Show that Pay is unavailable.
4. Open Command Center, inspect the review, and approve it.
5. Return to Risk and open Razorpay checkout.

### 4. Recovery and finance — 75 seconds

1. Use a failed Test Mode payment or a prepared failed transaction.
2. Open Recovery and run the supervisor.
3. Show failure classification, recovery probability, retry budget, policy decision, and fresh recovery order.
4. Complete the recovery checkout.
5. Open Finance and reconcile the settlement-pending transaction.

### 5. Evidence — 60 seconds

In Command Center, show:

- Money State Graph history;
- live agent registry and guardrails;
- durable supervisor traces and stop reasons;
- policy decisions and human approvals;
- circuit-breaker simulation;
- seeded recovery evaluation clearly labelled synthetic;
- agent telemetry and tamper-evident audit entries.

Close with: “Agents recommend. Policy decides. Verified evidence changes money state.”

## Honest answers for judges

- **Are the agents live?** Yes: every button calls backend decision code and persists real agent/supervisor runs. The current engines are deterministic, not an LLM.
- **Does it move real money?** No. The repository is configured for Razorpay Test Mode.
- **Is the evaluation merchant performance?** No. It is a deterministic seeded simulation for regression evidence.
- **What is autonomous?** State observation, specialist routing, risk/recovery recommendations, policy evaluation, and explicitly permitted order preparation. Customer payment, signed provider evidence, human gates, and settlement input remain external boundaries.
