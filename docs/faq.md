# Frequently Asked Questions (FAQ)

### Q1: Is RAVEN BOT X an Open Source project?
**No.** RAVEN BOT X is a **Source-Available** project licensed under the **PolyForm Noncommercial License 1.0.0**. You are permitted to inspect, modify, and run the software for personal, noncommercial, and educational purposes. Commercial use, resale, and commercial SaaS hosting are strictly prohibited without prior written permission.

### Q2: What services can the bot receive OTPs for?
The bot can extract verification codes for all global SMS traffic supported by the iVasms monetization portal, including WhatsApp, Telegram, TikTok, Meta (Facebook/Instagram), Apple, Google, and betting/gaming platforms.

### Q3: Why does the bot require cookies rather than an API key?
iVasms does not provide a public REST API for live traffic monetization feeds; the web portal utilizes authenticated session cookies protected by Cloudflare bot management. The bot emulates browser sessions to read received SMS streams in real-time.

### Q4: Can I run this bot on a VPS?
Yes, RAVEN BOT X runs reliably on standard Linux Virtual Private Servers (VPS). A lightweight 1 CPU, 1GB RAM server is sufficient for running the bot daemon and background workers.\n