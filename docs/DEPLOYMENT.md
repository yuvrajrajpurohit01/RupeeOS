# Deployment Guide

## Local containers

```bash
docker compose up --build
```

Set Razorpay Test Mode values in your shell or a root `.env` file before starting. The API healthcheck waits for `/health/ready`; the frontend starts after the API becomes ready.

## Environment variables

| Variable | Default | Purpose |
| --- | --- | --- |
| `RAZORPAY_KEY_ID` | empty | Test Mode public key ID |
| `RAZORPAY_KEY_SECRET` | empty | Test Mode server secret |
| `RAZORPAY_WEBHOOK_SECRET` | empty | Webhook HMAC secret |
| `RUPEEOS_DATABASE_URL` | `sqlite:///./rupeeos.db` | SQLAlchemy database URL |
| `RUPEEOS_CORS_ORIGINS` | `http://localhost:3000` | Comma-separated browser origins |
| `RUPEEOS_DEMO_MODE` | `true` | Enables failure-spike controls |
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | Browser-visible API base URL |

## Production checklist

- Set `RUPEEOS_DEMO_MODE=false`.
- Use a managed PostgreSQL database and schema migrations.
- Add authentication and separate operator/reviewer roles.
- Store secrets in the platform secret manager.
- Terminate TLS at a trusted ingress.
- Restrict CORS to the exact UI origin.
- Add rate limits and request-size limits at the edge.
- Run supervisor work through a durable queue with per-transaction leases.
- Export logs, metrics, traces, and security alerts.
- Configure backups and test recovery.
- Complete payment, privacy, and compliance review before Live Mode.
