# Security Policy

## Supported version

Security fixes are applied to the latest `main` branch.

## Reporting a vulnerability

Do not open a public issue for a suspected vulnerability involving credentials, payment signatures, webhook verification, authorization, personal data, or money movement. Contact the repository owner privately through the security-reporting channel configured on the GitHub repository. Include reproduction steps, affected endpoints, impact, and any suggested mitigation.

## Secret handling

- Never commit `.env`, Razorpay key secrets, webhook secrets, database credentials, or live payment data.
- Use Razorpay Test Mode for development and demonstrations.
- Rotate a credential immediately if it appears in a commit, log, screenshot, issue, or chat.
- Treat `NEXT_PUBLIC_*` variables as visible to every browser user.

## Scope warning

RupeeOS is a Buildathon project and is not certified for real-money production. See [docs/SECURITY_MODEL.md](docs/SECURITY_MODEL.md) for implemented controls and production gaps.
