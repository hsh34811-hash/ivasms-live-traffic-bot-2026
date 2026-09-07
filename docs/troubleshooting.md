# Troubleshooting & FAQ

This document covers common operational issues and their resolutions.

---

## 1. Cloudflare 403 Forbidden / Session Expired

### Symptoms:
Log outputs: `[iVasms] ❌ الكوكيز انتهت (رمز الاستجابة 403) — البوت هيوقف المحاولات لحد ما تبعت كوكيز جديدة`

### Cause:
The `cf_clearance` or `ivas_sms_session` cookie has expired, or Cloudflare detected an IP mismatch between the extracting browser and the server.

### Solution:
1. Open your browser on the same network (or VPN/Proxy) as your server.
2. Navigate to `https://www.ivasms.com/portal/sms/received`.
3. Re-export your cookies using `Cookie-Editor`.
4. Upload the new cookies via `/admin` -> `Cookies Manager` -> `Upload TXT / JSON`.

---

## 2. Bot Not Responding to Telegram Messages

### Symptoms:
The bot does not reply to `/start` or admin commands.

### Checklist:
- Ensure the bot process is running: `ps aux | grep "python3 main.py"`.
- Verify the Telegram Bot Token in `.env`.
- Check if another instance of the bot is running simultaneously (Telegram API allows only one active getUpdates connection per token).
- Review `bot.log` for polling timeout exceptions.

---

## 3. Database Locked Error (`sqlite3.OperationalError`)

### Symptoms:
Log outputs `sqlite3.OperationalError: database is locked`.

### Solution:
- RAVEN BOT X uses short connection lifecycles (`with sqlite3.connect(...)`).
- Ensure no external SQLite inspection tools hold exclusive write locks on `bot1.db`.\n