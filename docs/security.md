# Security & Privacy Policy

Security and session confidentiality are paramount for RAVEN BOT X.

---

## Threat Model & Protections

1. **Credential Isolation**:
   - The repository contains **no hardcoded production tokens or live session cookies**.
   - All credentials and bot tokens must be loaded via environment variables (`.env`).
   - Real database files (`bot1.db`), active session headers, and exported cookies are strictly excluded via `.gitignore`.

2. **Session Hijacking Prevention**:
   - Cloudflare clearance tokens and session cookies are stored locally on the host server in restricted JSON files.
   - Cookies are never exposed or transmitted in public Telegram groups or user messages.

3. **Input Sanitization**:
   - User inputs received via Telegram messages are sanitized prior to HTML formatting using `html.escape()` or `safe_html()`.
   - SQL queries utilize parameterized statements to prevent SQL injection vulnerabilities.

4. **Access Control**:
   - Administrative commands require verification against `ADMIN_IDS` and database administrator tables.
   - The primary bot owner cannot be removed by sub-administrators.

---

## Vulnerability Reporting

If you discover a security vulnerability, please do **NOT** open a public GitHub issue.

Please report vulnerabilities privately:
- **Lead Developer**: [@P_X_24](https://t.me/P_X_24) on Telegram.
- **Security Response Channel**: [@Raven_xx24](https://t.me/Raven_xx24).

We commit to acknowledging reports within 24 hours and providing a remediation patch in the shortest possible timeframe.\n