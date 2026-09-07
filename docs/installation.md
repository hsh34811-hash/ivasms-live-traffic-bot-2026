# Installation & Setup Guide

This guide describes how to deploy RAVEN BOT X on a Linux server or development workstation.

---

## Prerequisites

- **Operating System**: Linux (Ubuntu 20.04+, Debian 11+, CentOS 8+), macOS, or Windows with WSL.
- **Python**: Version 3.10 or higher.
- **SQLite**: Built into standard Python installations.
- **Git**: For version control.

---

## Step 1: Clone the Repository

```bash
git clone https://github.com/Raven-Team/raven-bot-x.git
cd raven-bot-x
```

---

## Step 2: Create a Virtual Environment

It is recommended to use an isolated Python virtual environment:

```bash
python3 -m venv venv
source venv/bin/activate
```

---

## Step 3: Install Dependencies

Install production requirements:

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

If you plan to run tests or benchmarks, install development dependencies:

```bash
pip install -r requirements-dev.txt
```

---

## Step 4: Verify Environment

Run the automated environment verification script:

```bash
python3 scripts/verify_environment.py
```

Expected output:
```text
==================================================
 RAVEN BOT X - Environment Verification
==================================================
[+] Python Version: 3.10+ ✅
[+] Package 'pyTelegramBotAPI': Installed ✅
[+] Package 'requests': Installed ✅
[+] Package 'beautifulsoup4': Installed ✅
[+] Package 'lxml': Installed ✅
[+] SQLite Engine: Operational ✅
...
🎉 Environment verification PASSED. Ready to run.
```

---

## Step 5: Configure Environment Variables

Create your `.env` configuration file from the provided template:

```bash
cp .env.example .env
```

Edit `.env` using your preferred editor (e.g. `nano .env`) to supply your Telegram Bot Token and administrator IDs. See [Configuration Guide](configuration.md) for detailed explanations.

---

## Step 6: Launch the Bot

### Foreground Execution (Development):
```bash
python3 main.py
```

### Background Daemon Execution (Production):
```bash
nohup python3 main.py > bot.log 2>&1 &
```

Check the log output:
```bash
tail -f bot.log
```\n