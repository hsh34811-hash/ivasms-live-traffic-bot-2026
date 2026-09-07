# Configuration Guide

RAVEN BOT X is configured using environment variables or a local `.env` file.

---

## Environment Variables Reference

| Variable | Type | Default Value | Description |
| :--- | :---: | :---: | :--- |
| `BOT_TOKEN` | string | *None (Required)* | Telegram Bot Token obtained from [@BotFather](https://t.me/BotFather). |
| `ADMIN_IDS` | string | `123456789` | Comma-separated list of Telegram User IDs granted full administrative access. |
| `DEFAULT_LANGUAGE` | string | `ar` | Default language for newly registered users (`ar`, `en`, `ur`, `ru`, `tr`, `fa`, `hi`). |
| `DATABASE_PATH` | string | `bot1.db` | Path to the SQLite database file. |
| `COOKIES_FILE` | string | `mafia_ck_4235.json` | Path to the active session cookies storage file. |
| `ACTIVE_HEADERS_FILE` | string | `active_headers.json` | Path to the browser header fingerprint file. |
| `REFRESH_INTERVAL` | integer | `6` | Polling interval in seconds for live SMS retrieval. |
| `REQUEST_TIMEOUT` | integer | `100` | HTTP request timeout in seconds for iVasms portal calls. |
| `IVASMS_BASE_URL` | string | `https://www.ivasms.com` | Target monetization platform base URL. |
| `IVASMS_RECEIVED_PATH` | string | `/portal/sms/received` | Relative endpoint for received SMS traffic. |

---

## Session Cookies Setup

To bypass Cloudflare protection on the target monetization portal, valid authenticated browser cookies are required:

1. Log into your account at `https://www.ivasms.com/login` using a desktop browser (Chrome, Firefox, or Edge).
2. Export your cookies in **JSON** or **Netscape** format using a browser extension (such as `Cookie-Editor` or `Get cookies.txt LOCALLY`).
3. Upload the exported file through the Admin Panel:
   - Send `/admin` to the bot in Telegram.
   - Navigate to **🍪 Cookies Manager (فحص وإدارة الكوكيز)**.
   - Tap **📤 Upload TXT / JSON (رفع ملف TXT أو كود JSON)** and send the file.
4. The bot will automatically validate the session and initialize the live stream worker.\n