# Usage Manual

This manual explains user interaction flows and administrative operations available in RAVEN BOT X.

---

## User Interaction

### 1. Starting the Bot (`/start`)
- When a user sends `/start`, the bot verifies mandatory channel subscriptions (if force subscription is active).
- Displays a clean, bilingual welcome banner and an interactive grid of available countries.
- If the user has an assigned Private Combo, it appears highlighted in green at the top.

### 2. Number Allocation & Details Screen
- Clicking any country button allocates a fresh, unused number for that country and service.
- The details screen displays:
  - **Assigned Number** (with single-tap copy format `+XXXXXXXXXXX`).
  - **Country & Flag**.
  - **Assigned Service** (e.g. WhatsApp, Telegram, TikTok, or All Apps).
  - **Live Status Indicator** (Waiting for incoming SMS).
- Buttons available:
  - `🔄 Change Number`: Releases current number and allocates a fresh one.
  - `🔙 Back`: Returns to country selection.

### 3. Automatic OTP Delivery
- When an SMS arrives for the user's number, the bot sends an immediate private notification:
  - Extracted OTP code displayed prominently in monospace.
  - Single-tap copy button for the verification code.
  - Service and timestamp details.

### 4. Language Selection
- Users can switch their interface language at any time by tapping `🌐 Language / اللغة`.
- Supported languages:
  - 🇸🇦 Arabic (`ar`)
  - 🇺🇸 English (`en`)
  - 🇵🇰 Urdu (`ur`)
  - 🇷🇺 Russian (`ru`)
  - 🇹🇷 Turkish (`tr`)
  - 🇮🇷 Persian (`fa`)
  - 🇮🇳 Hindi (`hi`)

---

## Administrative Operations (`/admin`)

Administrators (defined in `ADMIN_IDS` or promoted via the panel) have access to the control center:

1. **Maintenance Mode Toggle**: Instantly pauses user access with a friendly maintenance screen during updates.
2. **Combo Management**:
   - `Add Combo`: Add new country ranges.
   - `Delete Combo`: Remove inactive ranges.
   - `Customize Service`: Pin specific applications (WhatsApp, Telegram, etc.) to a combo.
3. **Live Stream Engine**:
   - Toggle automated live SMS streaming to channels or groups.
   - Filter by app: WhatsApp (WS), Telegram (TG), TikTok (TT), Meta (FB), Apple (AP), Google (GO), or Top Worldwide.
4. **Cookies Manager**:
   - Live health check of Cloudflare session cookies.
   - In-app cookie upload (TXT / JSON).
   - Historical message pull test by specific date.
5. **Admin Management**:
   - Add new administrators by Telegram User ID or forwarded message.
   - Revoke administrator privileges (main owner is protected).
6. **Broadcasting & User Management**:
   - Broadcast announcements to all active users.
   - Ban or unban specific user IDs.
   - Inspect user profiles and activity stats.\n