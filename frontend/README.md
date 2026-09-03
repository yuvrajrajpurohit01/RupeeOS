# RupeeOS Frontend

Next.js operator UI for the RupeeOS Money State Graph and durable agentic supervisor.

```powershell
Copy-Item .env.example .env.local
npm ci
npm run dev
```

Default API URL: `http://localhost:8000`.

The frontend does not simulate payment outcomes. Risk and Recovery invoke persisted supervisor runs, payment orders are created through FastAPI, Razorpay Standard Checkout opens in the browser, and successful checkout fields are verified by the backend. Command Center exposes the live agent registry, workflow traces, policy decisions, approvals, and audit evidence.

See the repository root `README.md` for the complete setup and Buildathon demo flow.
