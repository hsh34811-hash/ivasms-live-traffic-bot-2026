# System Architecture

RAVEN BOT X is architected as an asynchronous, event-driven multi-threaded system built on Python, `pyTelegramBotAPI`, and SQLite3.

---

## Layered Architecture

```text
+-------------------------------------------------------------+
|                      Presentation Layer                     |
|        Telegram Bot API (Inline Keyboards & Callbacks)       |
+-------------------------------------------------------------+
                               |
                               v
+-------------------------------------------------------------+
|                      Application Core                       |
|       Command Dispatcher | State Machine | Multilingual      |
|             (main.py, locales.py, country_data.py)          |
+-------------------------------------------------------------+
               |                               |
               v                               v
+-----------------------------+ +-----------------------------+
|      Persistence Layer      | |     Integration Engine      |
|  SQLite3 (bot1.db)          | |  ivasms_manager.py          |
|  - users, combos, groups    | |  - Cloudflare Session Mgmt  |
|  - force_sub, admins        | |  - Live Stream Worker       |
+-----------------------------+ +-----------------------------+
                                               |
                                               v
                                +-----------------------------+
                                |    External Infrastructure  |
                                |    iVasms Monetization API  |
                                +-----------------------------+
```

---

## Threading & Concurrency Model

RAVEN BOT X runs multiple concurrent daemon threads coordinated through thread-safe locks:

1. **Telegram Polling Thread**: Handles incoming user messages, callback queries, and command routing.
2. **Live Stream Monitor Thread (`live_stream_worker`)**:
   - Periodically polls the iVasms portal at configurable intervals (`REFRESH_INTERVAL`).
   - Parses the HTML table / AJAX response for new incoming SMS items.
   - Deduplicates messages using an in-memory hash set and persistent cache (`sent_live_messages.json`).
   - Dispatches matched messages to target groups or subscribed users.
3. **Hourly Group Reminder Thread (`hourly_group_reminder_worker`)**:
   - Runs every 3600 seconds.
   - Identifies active groups where the bot holds administrator rights.
   - Sends a temporary reminder message with self-destruct timer (60 seconds).
4. **Session Lock Guard (`_login_lock`)**:
   - Ensures only one thread attempts cookie refresh or portal login simultaneously.\n