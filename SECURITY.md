# Security Policy

## Supported Versions

Security updates and vulnerability remediation are actively maintained for the following release branch:

| Version | Supported |
| :--- | :---: |
| 2.0.x (Latest) | Yes |
| < 2.0.0 | No |

---

## Reporting a Vulnerability

We take the security of session data and bot infrastructure seriously. If you identify a security vulnerability, please **do NOT report it in public GitHub issues or discussions**.

### Contact Information
Please disclose vulnerabilities directly to the maintainers via Telegram:
- **Lead Developer**: [@P_X_24](https://t.me/P_X_24)
- **Security & Official Channel**: [@Raven_xx24](https://t.me/Raven_xx24)

### What to Include in Your Report
1. A detailed description of the vulnerability.
2. Steps to reproduce or proof-of-concept (PoC) code.
3. Potential impact on user data or session tokens.
4. Any proposed remediations.

We will acknowledge receipt of your report within 24 hours and maintain confidentiality until a patch is released.

---

## Secret Management & Hygiene

- Never commit real credentials, Telegram Bot Tokens, database files (`*.db`), or active cookies to git.
- All secrets must be provided through environment variables using `.env` as documented in [`.env.example`](.env.example).
- Ensure `.gitignore` remains configured to ignore `*.db`, `*.json` session dumps, and `.env` files.
