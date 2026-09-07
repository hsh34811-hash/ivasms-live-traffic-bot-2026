import time
import requests
import json
import re
import os
from datetime import datetime, date, timedelta
from urllib.parse import quote_plus
from pathlib import Path
import sqlite3
import telebot
from telebot import types
import threading
import traceback
import random
import itertools
import logging
from locales import (
    get_text,
    get_user_language,
    set_user_language,
    build_language_markup,
    build_admin_language_markup,
    SUPPORTED_LANGUAGES
)
import asyncio
import httpx
from bs4 import BeautifulSoup
from urllib.parse import urljoin


# منع تكرار رسالة انتهاء الكوكيز
_cookies_alert_sent = False

# منع تعارض login من مصادر متعددة
_login_lock = threading.Lock()
_login_in_progress = False
_cookies_expired = False  # لما الكوكيز تنتهي يوقف المحاولات


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
COOKIES_FILE = os.path.join(BASE_DIR, "mafia_ck_4235.json")
ACTIVE_HEADERS_FILE = os.path.join(BASE_DIR, "active_headers.json")
_last_cookies_update = None

DEFAULT_DESKTOP_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
    'Accept-Language': 'en-US,en;q=0.9,ar;q=0.8',
    'sec-ch-ua': '"Chromium";v="152", "Google Chrome";v="152", "Not-A.Brand";v="99"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"Linux"',
    'sec-fetch-dest': 'document',
    'sec-fetch-mode': 'navigate',
    'sec-fetch-site': 'none',
    'sec-fetch-user': '?1',
    'upgrade-insecure-requests': '1',
}

def get_active_headers():
    hdrs = dict(DEFAULT_DESKTOP_HEADERS)
    if os.path.exists(ACTIVE_HEADERS_FILE):
        try:
            with open(ACTIVE_HEADERS_FILE, 'r', encoding='utf-8') as f:
                saved = json.load(f)
                if isinstance(saved, dict) and 'User-Agent' in saved:
                    hdrs.update(saved)
        except Exception:
            pass
    return hdrs

def save_cookies_to_file(cookies_dict):
    with open(COOKIES_FILE, 'w', encoding='utf-8') as f:
        json.dump(cookies_dict, f, ensure_ascii=False, indent=2)

def load_cookies_from_file():
    import glob
    candidates = glob.glob("/home/obs/Downloads/*cookie*.txt")
    if candidates:
        candidates.sort(key=os.path.getmtime, reverse=True)
        latest_txt = candidates[0]
        try:
            with open(latest_txt, 'r', encoding='utf-8') as f:
                content = f.read()
            parsed = parse_cookies_input(content)
            if parsed:
                return parsed
        except Exception:
            pass

    if os.path.exists(COOKIES_FILE):
        try:
            with open(COOKIES_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"[!] Error loading cookies from file: {e}")
    return None

def parse_cookies_input(raw_text):
    """تحليل الكوكيز من نص JSON أو ملف Netscape (.txt)"""
    raw_text = raw_text.strip()
    if not raw_text:
        raise ValueError("النص أو الملف فارغ.")

    # 1. تجربة تحليل JSON أولاً
    if raw_text.startswith('[') or raw_text.startswith('{'):
        try:
            data = json.loads(raw_text)
            if isinstance(data, list):
                cookies = []
                for c in data:
                    if isinstance(c, dict) and 'name' in c and 'value' in c:
                        cookies.append({
                            'name': c['name'],
                            'value': c['value'],
                            'domain': c.get('domain', 'www.ivasms.com').lstrip('.'),
                            'path': c.get('path', '/')
                        })
                if cookies:
                    return cookies
            elif isinstance(data, dict):
                return [{'name': k, 'value': str(v), 'domain': 'www.ivasms.com', 'path': '/'} for k, v in data.items()]
        except Exception:
            pass

    # 2. تجربة تحليل تنسيق Netscape (Tab-separated)
    cookies = []
    for line in raw_text.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith('#HttpOnly_'):
            line = line[len('#HttpOnly_'):]
        elif line.startswith('#'):
            continue
        parts = line.split('\t')
        if len(parts) >= 7:
            domain = parts[0].lstrip('.')
            path = parts[2]
            name = parts[5].strip()
            value = parts[6].strip()
            cookies.append({
                'name': name,
                'value': value,
                'domain': domain,
                'path': path
            })
    if cookies:
        return cookies

    raise ValueError("تعذر استخراج الكوكيز. تأكد من رفع ملف .txt بصيغة Netscape صالحة أو لصق كود JSON صحيح.")

UA_PROFILES = [
    {
        "name": "Yandex Browser Mobile (Android)",
        "ua": "Mozilla/5.0 (Linux; Android 14; Mobile) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Mobile Safari/537.36 YaBrowser/24.7.0.0 Mobile",
        "mobile": "?1",
        "platform": '"Android"',
        "brands": '"Chromium";v="128", "Not;A=Brand";v="24", "Yandex";v="24"'
    },
    {
        "name": "Yandex Browser Mobile v24.4 (Android)",
        "ua": "Mozilla/5.0 (Linux; Android 13; Mobile) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Mobile Safari/537.36 YaBrowser/24.4.0.0 Mobile",
        "mobile": "?1",
        "platform": '"Android"',
        "brands": '"Chromium";v="126", "Not;A=Brand";v="24", "Yandex";v="24"'
    },
    {
        "name": "Yandex Browser Desktop Mode (Android/Linux)",
        "ua": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 YaBrowser/24.7.0.0 Safari/537.36",
        "mobile": "?0",
        "platform": '"Linux"',
        "brands": '"Chromium";v="128", "Not;A=Brand";v="24", "Yandex";v="24"'
    },
    {
        "name": "Yandex Browser Desktop (Windows PC)",
        "ua": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 YaBrowser/24.7.0.0 Safari/537.36",
        "mobile": "?0",
        "platform": '"Windows"',
        "brands": '"Chromium";v="128", "Not;A=Brand";v="24", "Yandex";v="24"'
    },
    {
        "name": "Desktop Linux Chrome",
        "ua": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36",
        "mobile": "?0",
        "platform": '"Linux"',
        "brands": '"Chromium";v="152", "Google Chrome";v="152", "Not-A.Brand";v="99"'
    },
    {
        "name": "Desktop Windows Chrome",
        "ua": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
        "mobile": "?0",
        "platform": '"Windows"',
        "brands": '"Chromium";v="130", "Google Chrome";v="130", "Not?A_Brand";v="99"'
    },
    {
        "name": "Android Mobile Chrome (Kiwi)",
        "ua": "Mozilla/5.0 (Linux; Android 14; Mobile) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36",
        "mobile": "?1",
        "platform": '"Android"',
        "brands": '"Chromium";v="130", "Google Chrome";v="130", "Not?A_Brand";v="99"'
    },
    {
        "name": "Android Kiwi (Generic)",
        "ua": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Mobile Safari/537.36",
        "mobile": "?1",
        "platform": '"Android"',
        "brands": '"Chromium";v="128", "Not;A=Brand";v="24", "Google Chrome";v="128"'
    },
    {
        "name": "iPhone Safari Mobile",
        "ua": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1",
        "mobile": "?1",
        "platform": '"iOS"',
        "brands": None
    }
]

def verify_and_test_cookies(cookies_list, preferred_ua=None):
    """فحص واختبار الكوكيز مباشرة مع موقع ivasms.com مع تجربة بصمات متعددة (Yandex, Kiwi, Chrome, Mobile & PC)"""
    if not cookies_list:
        return False, "قائمة الكوكيز فارغة.", None, None

    had_403 = False
    last_err = None

    profiles_to_test = list(UA_PROFILES)
    if preferred_ua:
        is_mob = any(k in preferred_ua for k in ["Mobile", "Android", "iPhone"])
        plat = '"Android"' if "Android" in preferred_ua else ('"iOS"' if "iPhone" in preferred_ua else ('"Windows"' if "Windows" in preferred_ua else '"Linux"'))
        profiles_to_test.insert(0, {
            "name": f"User Custom UA ({preferred_ua[:35]}...)",
            "ua": preferred_ua,
            "mobile": "?1" if is_mob else "?0",
            "platform": plat,
            "brands": '"Chromium";v="128", "Not;A=Brand";v="24", "Yandex";v="24"' if "YaBrowser" in preferred_ua else None
        })

    for profile in profiles_to_test:
        test_session = requests.Session()
        hdrs = {
            'User-Agent': profile['ua'],
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'en-US,en;q=0.9,ar;q=0.8',
            'sec-fetch-dest': 'document',
            'sec-fetch-mode': 'navigate',
            'sec-fetch-site': 'none',
            'sec-fetch-user': '?1',
            'upgrade-insecure-requests': '1',
        }
        if profile.get('brands'):
            hdrs['sec-ch-ua'] = profile['brands']
        if profile.get('mobile'):
            hdrs['sec-ch-ua-mobile'] = profile['mobile']
        if profile.get('platform'):
            hdrs['sec-ch-ua-platform'] = profile['platform']

        test_session.headers.update(hdrs)

        if isinstance(cookies_list, list):
            for c in cookies_list:
                domain = c.get('domain', 'www.ivasms.com').lstrip('.')
                test_session.cookies.set(c['name'], c['value'], domain=domain, path=c.get('path', '/'))
        elif isinstance(cookies_list, dict):
            for name, value in cookies_list.items():
                test_session.cookies.set(name, value, domain='www.ivasms.com', path='/')

        try:
            resp = test_session.get("https://www.ivasms.com/portal/sms/received", timeout=20, allow_redirects=True)
            if "login" in resp.url.lower():
                return False, "تم التحويل لصفحة تسجيل الدخول (الكوكيز منتهية أو غير مسجلة دخول).", None, None

            if resp.status_code == 403:
                had_403 = True
                continue

            if resp.status_code != 200:
                last_err = f"استجابة غير متوقعة من الموقع (رمز الحالة: {resp.status_code})."
                continue

            soup = BeautifulSoup(resp.text, 'html.parser')
            csrf_meta = soup.find('meta', {'name': 'csrf-token'})
            csrf_token = csrf_meta.get('content') if csrf_meta else None

            if not csrf_token:
                match = re.search(r'name=["\'](?:_token|csrf-token)["\']\s+value=["\']([^"\']+)["\']', resp.text)
                if match:
                    csrf_token = match.group(1)

            if not csrf_token:
                return False, "تم فتح صفحة الرسائل ولكن تعذر استخراج رمز الحماية CSRF Token.", None, None

            today = datetime.now()
            payload = {
                'from': (today - timedelta(days=3)).strftime('%m/%d/%Y'),
                'to': today.strftime('%m/%d/%Y'),
                '_token': csrf_token
            }
            api_headers = {
                'Referer': 'https://www.ivasms.com/portal/sms/received',
                'X-Requested-With': 'XMLHttpRequest'
            }
            api_resp = test_session.post("https://www.ivasms.com/portal/sms/received/getsms", headers=api_headers, data=payload, timeout=20)
            if api_resp.status_code == 200:
                return True, f"تم فحص الاتصال باللوحة وبوابة الرسائل بنجاح 100% عبر بصمة ({profile['name']})!", csrf_token, hdrs
            else:
                return True, f"تم تسجيل الدخول بنجاح عبر ({profile['name']}) واستخراج CSRF (رمز بوابة الرسائل: {api_resp.status_code}).", csrf_token, hdrs

        except requests.exceptions.RequestException as e:
            last_err = f"خطأ أثناء الاتصال بالموقع: {str(e)}"
        except Exception as e:
            last_err = f"حدث خطأ غير متوقع: {str(e)}"

    if had_403:
        err_msg = (
            "تم حظر الاتصال بحماية Cloudflare (رمز 403).\n\n"
            "💡 <b>أسباب حدوث هذا الخطأ عند الرفع من الهاتف:</b>\n"
            "1️⃣ <b>بصمة المتصفح:</b> متصفح الهاتف يرسل بصمة هاتف، لتجنب ذلك افتح متصفح Kiwi وفعّل خيار «الموقع المخصص للكمبيوتر (Desktop site)» قبل تسجيل الدخول وتصدير الكوكيز.\n"
            "2️⃣ <b>عنوان الـ IP (شبكة 4G):</b> إذا كان هاتفك على باقة الهاتف يختلف عنوان الـ IP عن سيرفر البوت فيتم الحظر؛ احرص على استخدام نفس شبكة الواي فاي (Wi-Fi)."
        )
        return False, err_msg, None, None

    return False, last_err or "حدث خطأ غير متوقع أثناء فحص الكوكيز.", None, None

def apply_cookies(cookies_list_or_dict, csrf_token=None, custom_headers=None):
    dash    = IVASMS_DASHBOARD
    session = dash['session']
    session.cookies.clear()
    
    if custom_headers:
        session.headers.update(custom_headers)
        try:
            with open(ACTIVE_HEADERS_FILE, 'w', encoding='utf-8') as f:
                json.dump(custom_headers, f, indent=2)
        except Exception as e:
            print(f"[!] Error saving active headers: {e}")
    else:
        session.headers.update(get_active_headers())

    print(f"[DEBUG] apply_cookies - نوع البيانات: {type(cookies_list_or_dict)}")
    if isinstance(cookies_list_or_dict, list):
        print(f"[DEBUG] عدد الكوكيز: {len(cookies_list_or_dict)}")
        for c in cookies_list_or_dict:
            name   = c['name']
            value  = c['value']
            domain = c.get('domain', 'www.ivasms.com').lstrip('.')
            session.cookies.set(name, value, domain=domain, path=c.get('path', '/'))
        save_cookies_to_file(cookies_list_or_dict)
    else:
        for name, value in cookies_list_or_dict.items():
            session.cookies.set(name, value, domain='www.ivasms.com', path='/')
        save_cookies_to_file(cookies_list_or_dict)

    if csrf_token:
        dash['csrf_token'] = csrf_token
    dash['is_logged_in'] = True
    dash['cookies'] = session.cookies.get_dict()
    dash['last_check'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    global _cookies_expired, _cookies_alert_sent, _last_cookies_update
    _cookies_expired = False
    _cookies_alert_sent = False
    _last_cookies_update = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[DEBUG] تم تفعيل الكوكيز بنجاح ✅ _cookies_expired = False")
    return True


# ======================
# 🖥️ إعداد اللوحة الوحيدة (iVasms)
# ======================

IVASMS_DASHBOARD = {
    "name": "iVasms",
    "type": "ivasms",
    "login_url": "https://www.ivasms.com/login",
    "base_url": "https://www.ivasms.com",
    "sms_api_endpoint": "https://www.ivasms.com/portal/sms/received/getsms",
    "username": "user@example.com",
    "password": "REDACTED_PASSWORD",
    "session": requests.Session(),
    "is_logged_in": False,
    "cookies": None,
    "csrf_token": None,
    "last_check": None
}

# ======================
# 🔧 إعدادات عامة
# ======================
USERNAME = os.getenv("IVASMS_USERNAME", "user@example.com")
PASSWORD = os.getenv("IVASMS_PASSWORD", "REDACTED_PASSWORD")
BOT_TOKEN = os.getenv("BOT_TOKEN", "REDACTED_TELEGRAM_TOKEN")
CHAT_IDS = [
    "-1001234567890",
]
REFRESH_INTERVAL = int(os.getenv("REFRESH_INTERVAL", "6"))
TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "100"))
MAX_RETRIES = 5
RETRY_DELAY = 5

# مؤشرات الأعمدة للوحة التقليدية
IDX_DATE = 0
IDX_NUMBER = 2
IDX_SMS = 5
SENT_MESSAGES_FILE = "sent_messages_bot1.json"

_env_admins = os.getenv("ADMIN_IDS", "")
ADMIN_IDS = [int(x.strip()) for x in _env_admins.split(",") if x.strip().isdigit()] if _env_admins else [123456789]
DB_PATH = os.getenv("DATABASE_PATH", "bot1.db")
FORCE_SUB_CHANNEL = None
FORCE_SUB_ENABLED = False
BOT_ACTIVE = True 

if not BOT_TOKEN:
    raise SystemExit("❌ BOT_TOKEN must be set in Secrets (Environment Variables)")
if not CHAT_IDS:
    raise SystemExit("❌ CHAT_IDS must be configured")
if not USERNAME or not PASSWORD:
    print("⚠️  WARNING: SITE_USERNAME and SITE_PASSWORD not set in Secrets")
    print("⚠️  Bot will continue but login may fail")

# ======================
# 🌍 رموز الدول والتطبيقات الذكية
# ======================
from country_data import (
    COUNTRY_CODES,
    APP_SHORT_CODES,
    get_app_badge,
    get_service_display,
    get_country_details_smart
)

# ======================
# 🧰 دوال إدارة قاعدة البيانات (محدثة)
# ======================
def get_setting(key):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT value FROM bot_settings WHERE key=?", (key,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None

def set_setting(key, value):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("REPLACE INTO bot_settings (key, value) VALUES (?, ?)", (key, value))
    conn.commit()
    conn.close()

# ======================
# 🧠 إنشاء قاعدة البيانات (مع جداول جديدة)
# ======================
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            country_code TEXT,
            assigned_number TEXT,
            is_banned INTEGER DEFAULT 0,
            private_combo_country TEXT DEFAULT NULL
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS combos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            country_code TEXT,
            combo_index INTEGER DEFAULT 1,
            numbers TEXT,
            UNIQUE(country_code, combo_index)
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS otp_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            number TEXT,
            otp TEXT,
            full_message TEXT,
            timestamp TEXT,
            assigned_to INTEGER
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS dashboards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            base_url TEXT,
            ajax_path TEXT,
            login_page TEXT,
            login_post TEXT,
            username TEXT,
            password TEXT
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS bot_settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS private_combos (
            user_id INTEGER,
            country_code TEXT,
            numbers TEXT,
            PRIMARY KEY (user_id, country_code)
        )
    ''')
    # ✅ جدول القنوات الجديدة
    c.execute('''
        CREATE TABLE IF NOT EXISTS force_sub_channels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_url TEXT UNIQUE NOT NULL,
            description TEXT DEFAULT '',
            enabled INTEGER DEFAULT 1
        )
    ''')
    # ✅ جدول الأدمنية
    c.execute('''
        CREATE TABLE IF NOT EXISTS admins (
            user_id INTEGER PRIMARY KEY,
            added_at TEXT,
            added_by INTEGER
        )
    ''')
    for admin_id in ADMIN_IDS:
        c.execute("INSERT OR IGNORE INTO admins (user_id, added_at, added_by) VALUES (?, datetime('now'), 0)", (admin_id,))

    # تهيئة الإعدادات القديمة (للتوافق مع البوت القديم)
    c.execute("INSERT OR IGNORE INTO bot_settings (key, value) VALUES ('force_sub_channel', '')")
    c.execute("INSERT OR IGNORE INTO bot_settings (key, value) VALUES ('force_sub_enabled', '0')")

    # 🔄 نقل القناة القديمة (إن وُجدت) تلقائيًا إلى الجدول الجديد
    c.execute("SELECT value FROM bot_settings WHERE key = 'force_sub_channel'")
    old_channel = c.fetchone()
    if old_channel and old_channel[0].strip():
        channel = old_channel[0].strip()
        # تأكد أنها ليست مكررة في الجدول الجديد
        c.execute("SELECT 1 FROM force_sub_channels WHERE channel_url = ?", (channel,))
        if not c.fetchone():
            enabled = 1 if get_setting("force_sub_enabled") == "1" else 0
            c.execute("INSERT INTO force_sub_channels (channel_url, description, enabled) VALUES (?, ?, ?)",
                      (channel, "القناة الأساسية", enabled))

    # ✅ جدول المجموعات المسجلة للتذكير الدوري
    c.execute('''
        CREATE TABLE IF NOT EXISTS bot_groups (
            chat_id TEXT PRIMARY KEY,
            title TEXT,
            is_admin INTEGER DEFAULT 1,
            added_at TEXT
        )
    ''')
    for cid in CHAT_IDS:
        c.execute("INSERT OR IGNORE INTO bot_groups (chat_id, title, is_admin, added_at) VALUES (?, ?, 1, datetime('now'))", (str(cid), "Default Group"))

    conn.commit()
    conn.close()

init_db()

# ======================
# 🧰 دوال إدارة قاعدة البيانات (محدثة)
# ======================

def get_user(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    return row

def save_user(user_id, username="", first_name="", last_name="", country_code=None, assigned_number=None, private_combo_country=None, lang=None):
    """
    يحفظ أو يحدّث بيانات المستخدم مع الحفاظ التام على لغة المستخدم وحالة الحظر والبيانات الأخرى.
    """
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    existing_data = get_user(user_id)
    if existing_data:
        if not username:
            username = existing_data[1]
        if not first_name:
            first_name = existing_data[2]
        if not last_name:
            last_name = existing_data[3]
        if country_code is None:
            country_code = existing_data[4]
        if assigned_number is None:
            assigned_number = existing_data[5]
        if private_combo_country is None:
            private_combo_country = existing_data[7]
        if lang is None and len(existing_data) > 8:
            lang = existing_data[8]

    if not lang:
        lang = "ar"

    c.execute("""
        INSERT INTO users (user_id, username, first_name, last_name, country_code, assigned_number, is_banned, private_combo_country, lang)
        VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            username = CASE WHEN excluded.username != '' THEN excluded.username ELSE users.username END,
            first_name = CASE WHEN excluded.first_name != '' THEN excluded.first_name ELSE users.first_name END,
            last_name = CASE WHEN excluded.last_name != '' THEN excluded.last_name ELSE users.last_name END,
            country_code = COALESCE(excluded.country_code, users.country_code),
            assigned_number = COALESCE(excluded.assigned_number, users.assigned_number),
            private_combo_country = COALESCE(excluded.private_combo_country, users.private_combo_country),
            lang = COALESCE(excluded.lang, users.lang)
    """, (
        user_id,
        username,
        first_name,
        last_name,
        country_code,
        assigned_number,
        private_combo_country,
        lang
    ))
    conn.commit()
    conn.close()

def ban_user(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE users SET is_banned=1 WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()

def unban_user(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE users SET is_banned=0 WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()

def is_banned(user_id):
    user = get_user(user_id)
    return user and user[6] == 1
    
def is_maintenance_mode():
    return not BOT_ACTIVE

def set_maintenance_mode(status):
    global BOT_ACTIVE
    BOT_ACTIVE = not status
    
def get_all_users():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT user_id FROM users WHERE is_banned=0")
    users = [row[0] for row in c.fetchall()]
    conn.close()
    return users

def get_combo(country_code, combo_index=1, user_id=None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    raw_data = None
    if user_id:
        c.execute("SELECT numbers FROM private_combos WHERE user_id=? AND country_code=?", (user_id, country_code))
        row = c.fetchone()
        if row and row[0]:
            raw_data = row[0]
    if raw_data is None:
        c.execute("SELECT numbers FROM combos WHERE country_code=? AND combo_index=?", (country_code, combo_index))
        row = c.fetchone()
        if row and row[0]:
            raw_data = row[0]
    conn.close()

    if not raw_data:
        return []

    try:
        data = json.loads(raw_data)
        if isinstance(data, list):
            return [str(x).strip() for x in data if str(x).strip()]
        return [str(data).strip()]
    except Exception:
        return [line.strip() for line in str(raw_data).splitlines() if line.strip()]

def save_combo(country_code, numbers, user_id=None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    if user_id:
        c.execute("REPLACE INTO private_combos (user_id, country_code, numbers) VALUES (?, ?, ?)",
                  (user_id, country_code, json.dumps(numbers)))
    else:
        # البحث عن آخر combo_index لهذه الدولة
        c.execute("SELECT MAX(combo_index) FROM combos WHERE country_code=?", (country_code,))
        max_index = c.fetchone()[0]
        next_index = 1 if max_index is None else max_index + 1
        
        c.execute("INSERT INTO combos (country_code, combo_index, numbers) VALUES (?, ?, ?)",
                  (country_code, next_index, json.dumps(numbers)))
    
    conn.commit()
    conn.close()

def get_combo_service(country_code, combo_index=1, user_id=None):
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        svc = None
        if user_id:
            c.execute("SELECT service FROM private_combos WHERE user_id=? AND country_code=?", (user_id, country_code))
            row = c.fetchone()
            if row and row[0]:
                svc = row[0]
        if not svc:
            c.execute("SELECT service FROM combos WHERE country_code=? AND combo_index=?", (country_code, combo_index))
            row = c.fetchone()
            if row and row[0]:
                svc = row[0]
        conn.close()
        return svc or "All Apps"
    except Exception:
        return "All Apps"

def set_combo_service(country_code, combo_index=1, service="All Apps", user_id=None):
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        if user_id:
            c.execute("UPDATE private_combos SET service=? WHERE user_id=? AND country_code=?", (service, user_id, country_code))
        else:
            c.execute("UPDATE combos SET service=? WHERE country_code=? AND combo_index=?", (service, country_code, combo_index))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error setting combo service: {e}")
        return False

def delete_combo(country_code, combo_index=None, user_id=None):
    """
    دالة حذف كومبو مع معالجة أخطاء قاعدة البيانات
    """
    conn = None
    try:
        # ⚠️ استخدم timeout كبير و check_same_thread=False
        conn = sqlite3.connect(DB_PATH, timeout=30.0, check_same_thread=False)
        c = conn.cursor()
        
        if user_id:
            c.execute("DELETE FROM private_combos WHERE user_id=? AND country_code=?", (user_id, country_code))
        elif combo_index:
            c.execute("DELETE FROM combos WHERE country_code=? AND combo_index=?", (country_code, combo_index))
        else:
            c.execute("DELETE FROM combos WHERE country_code=?", (country_code,))
        
        conn.commit()
        print(f"✅ تم حذف كومبو: {country_code} (index: {combo_index})")
        return True
        
    except sqlite3.Error as e:
        print(f"❌ خطأ SQLite في delete_combo: {e}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()

def get_all_combos():
    """ترجع قائمة من (country_code, combo_index)"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT country_code, combo_index FROM combos ORDER BY country_code, combo_index")
    combos = c.fetchall()
    conn.close()
    return combos  # [(country_code, combo_index), ...]

def assign_number_to_user(user_id, number):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE users SET assigned_number=? WHERE user_id=?", (number, user_id))
    conn.commit()
    conn.close()

def get_user_by_number(number):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT user_id FROM users WHERE assigned_number=?", (number,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None

def log_otp(number, otp, full_message, assigned_to=None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO otp_logs (number, otp, full_message, timestamp, assigned_to) VALUES (?, ?, ?, ?, ?)",
              (number, otp, full_message, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), assigned_to))
    conn.commit()
    conn.close()

def release_number(old_number):
    if not old_number:
        return
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE users SET assigned_number=NULL WHERE assigned_number=?", (old_number,))
    conn.commit()
    conn.close()

def get_otp_logs():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM otp_logs")
    logs = c.fetchall()
    conn.close()
    return logs

def get_user_info(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    row = c.fetchone()
    conn.close()
    return row

# --- دوال إدارة قنوات الاشتراك الإجباري (متعددة) ---
def get_all_force_sub_channels(enabled_only=True):
    """جلب القنوات (المفعلة فقط أو جميعها)"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    if enabled_only:
        c.execute("SELECT id, channel_url, description FROM force_sub_channels WHERE enabled = 1 ORDER BY id")
    else:
        c.execute("SELECT id, channel_url, description FROM force_sub_channels ORDER BY id")
    rows = c.fetchall()
    conn.close()
    return rows

def add_force_sub_channel(channel_url, description=""):
    """إضافة قناة جديدة (لا تسمح بالتكرار)"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute("INSERT INTO force_sub_channels (channel_url, description, enabled) VALUES (?, ?, 1)",
                  (channel_url.strip(), description.strip()))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False  # قناة مكررة
    finally:
        conn.close()

def delete_force_sub_channel(channel_id):
    """حذف قناة بالرقم التعريفي"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM force_sub_channels WHERE id = ?", (channel_id,))
    changed = c.rowcount > 0
    conn.commit()
    conn.close()
    return changed

def toggle_force_sub_channel(channel_id):
    """تفعيل/تعطيل قناة"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE force_sub_channels SET enabled = 1 - enabled WHERE id = ?", (channel_id,))
    conn.commit()
    conn.close()

# ======================
# 🔐 دوال الاشتراك الإجباري
# ======================
def force_sub_check(user_id):
    """التحقق من اشتراك المستخدم في **جميع** القنوات المُفعَّلة"""
    channels = get_all_force_sub_channels(enabled_only=True)
    if not channels:
        return True  # لا توجد قنوات → لا يوجد تحقق

    for _, url, _ in channels:
        try:
            # توحيد التنسيق: @xxx بدل https://t.me/xxx
            if url.startswith("https://t.me/"):
                ch = "@" + url.split("/")[-1]
            elif url.startswith("@"):
                ch = url
            else:
                continue  # تجاهل الروابط غير الصحيحة
            member = bot.get_chat_member(ch, user_id)
            if member.status not in ["member", "administrator", "creator"]:
                return False
        except Exception as e:
            print(f"[!] خطأ في التحقق من القناة {url}: {e}")
            return False  # أي فشل = غير مشترك
    return True

def force_sub_markup():
    """إنشاء زر لكل قناة مُفعَّلة + زر التحقق"""
    channels = get_all_force_sub_channels(enabled_only=True)
    if not channels:
        return None

    markup = types.InlineKeyboardMarkup()
    for _, url, desc in channels:
        text = f"📢 {desc}" if desc else "📢 اشترك في القناة"
        markup.add(types.InlineKeyboardButton(text, url=url, style='primary'))
    markup.add(types.InlineKeyboardButton("✅ تحقق من الاشتراك", callback_data="check_sub", style='success'))
    return markup

# ======================
# 🤖 إنشاء بوت Telegram
# ======================
bot = telebot.TeleBot(BOT_TOKEN)

# ======================
# 🎮 وظائف البوت التفاعلي
def get_all_admins():
    """جلب جميع معرفات الأدمنية من قاعدة البيانات مدمجة مع المعرفات الأساسية"""
    admins = set(ADMIN_IDS)
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("CREATE TABLE IF NOT EXISTS admins (user_id INTEGER PRIMARY KEY, added_at TEXT, added_by INTEGER)")
        c.execute("SELECT user_id FROM admins")
        rows = c.fetchall()
        for r in rows:
            admins.add(r[0])
        conn.close()
    except Exception as e:
        print(f"Error fetching admins: {e}")
    return list(admins)

def add_admin_db(user_id, added_by=0):
    """إضافة أدمن جديد إلى قاعدة البيانات"""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("CREATE TABLE IF NOT EXISTS admins (user_id INTEGER PRIMARY KEY, added_at TEXT, added_by INTEGER)")
        c.execute("INSERT OR REPLACE INTO admins (user_id, added_at, added_by) VALUES (?, datetime('now'), ?)", (user_id, added_by))
        conn.commit()
        conn.close()
        if user_id not in ADMIN_IDS:
            ADMIN_IDS.append(user_id)
        return True
    except Exception as e:
        print(f"Error adding admin: {e}")
        return False

def remove_admin_db(user_id):
    """حذف أدمن من قاعدة البيانات (مع حماية المالك الأساسي)"""
    if user_id == 123456789:
        return False, "owner"
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("DELETE FROM admins WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()
        if user_id in ADMIN_IDS and user_id != 123456789:
            ADMIN_IDS.remove(user_id)
        return True, "ok"
    except Exception as e:
        print(f"Error removing admin: {e}")
        return False, str(e)

def get_admins_details():
    """جلب تفاصيل جميع الأدمنية للعرض"""
    details = []
    details.append({'user_id': 123456789, 'is_owner': True, 'added_at': 'Primary Owner', 'added_by': 0})
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("CREATE TABLE IF NOT EXISTS admins (user_id INTEGER PRIMARY KEY, added_at TEXT, added_by INTEGER)")
        c.execute("SELECT user_id, added_at, added_by FROM admins")
        rows = c.fetchall()
        for r in rows:
            if r[0] != 123456789:
                details.append({'user_id': r[0], 'is_owner': False, 'added_at': r[1] or 'N/A', 'added_by': r[2] or 0})
        conn.close()
    except Exception as e:
        print(f"Error getting admin details: {e}")
    return details

def is_admin(user_id):
    return user_id in get_all_admins()

def safe_html(text):
    """تقوم بتنظيف النص من علامات HTML غير الصالحة"""
    if not text:
        return ""
    # استبدال علامات HTML ببدائل آمنة
    text = str(text)
    text = text.replace('&', '&amp;')
    text = text.replace('<', '&lt;')
    text = text.replace('>', '&gt;')
    text = text.replace('"', '&quot;')
    return text

def save_group_chat(chat_id, title=""):
    """حفظ أو تحديث بيانات المجموعة في قاعدة البيانات"""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("""
            INSERT INTO bot_groups (chat_id, title, is_admin, added_at)
            VALUES (?, ?, 1, datetime('now'))
            ON CONFLICT(chat_id) DO UPDATE SET title=excluded.title
        """, (str(chat_id), str(title or 'Group')))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[Groups] Error saving group {chat_id}: {e}")

def get_all_bot_groups():
    """جلب جميع المجموعات المسجلة للبوت"""
    groups = []
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT chat_id, title FROM bot_groups")
        rows = c.fetchall()
        conn.close()
        for r in rows:
            groups.append((r[0], r[1]))
    except Exception:
        pass
    # التأكد دائماً من وجود المجموعات الأساسية والمحددة في الإعدادات
    for cid in CHAT_IDS:
        if str(cid) not in [g[0] for g in groups]:
            groups.append((str(cid), "Default Group"))
    try:
        ls_id = get_live_stream_chat_id()
        if ls_id and str(ls_id) not in [g[0] for g in groups]:
            groups.append((str(ls_id), "Live Stream Group"))
    except Exception:
        pass
    return groups

@bot.my_chat_member_handler()
def handle_my_chat_member(update):
    """رصد إضافة البوت لمجموعة وترقيته لمشرف تلقائياً"""
    try:
        chat = update.chat
        if chat.type in ['group', 'supergroup']:
            status = update.new_chat_member.status
            if status in ['administrator', 'creator']:
                save_group_chat(chat.id, chat.title)
                print(f"[Groups] ➕ البوت مشرف في المجموعة: {chat.title} ({chat.id})")
    except Exception as e:
        print(f"[Groups] خطأ في تحديث حالة العضوية: {e}")

    
@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    lang = get_user_language(user_id)


    # لو مستخدم عادي والكوكيز منتهية يشوف رسالة صيانة
    if not is_admin(user_id) and not IVASMS_DASHBOARD.get('is_logged_in', False):
        maintenance_caption = get_text("maintenance_caption", lang)
        maintenance_photo = "https://i.ibb.co/2352v1FN/file-000000004f20720aaa70039fcd26faab-1.png"
        try:
            bot.send_photo(chat_id, maintenance_photo, caption=maintenance_caption, parse_mode="HTML")
        except Exception:
            bot.send_message(chat_id, maintenance_caption, parse_mode="HTML")
        return

    # 1. فحص وضع الصيانة (Maintenance Mode) مع صورة
    if is_maintenance_mode() and not is_admin(user_id):
        maintenance_caption = get_text("maintenance_caption", lang)
        maintenance_photo = "https://i.ibb.co/2352v1FN/file-000000004f20720aaa70039fcd26faab-1.png" 
        try:
            bot.send_photo(
                chat_id, 
                maintenance_photo, 
                caption=maintenance_caption, 
                parse_mode="HTML"
            )
        except:
            bot.send_message(chat_id, maintenance_caption, parse_mode="HTML")
        return

    # 2. فحص الحظر (Banned Users)
    if is_banned(user_id):
        bot.reply_to(message, get_text("banned_user", lang), parse_mode="HTML")
        return

    # 3. فحص الاشتراك الإجباري (Force Subscribe)
    if not force_sub_check(user_id):
        markup = force_sub_markup()
        if markup:
            bot.send_message(chat_id, get_text("force_sub_alert", lang), parse_mode="HTML", reply_markup=markup)
        else:
            bot.send_message(chat_id, "<b>🔒 الاشتراك الإجباري مفعل لكن لم يتم تحديد قناة!</b>", parse_mode="HTML")
        return

    # 4. حفظ المستخدم الجديد وإشعار الإدارة
    if not get_user(user_id):
        save_user(
            user_id,
            username=message.from_user.username or "",
            first_name=message.from_user.first_name or "",
            last_name=message.from_user.last_name or ""
        )
        for admin in ADMIN_IDS:
            try:
                caption = (
                    f"👤 <b>مستخدم جديد انضم للبوت:</b>\n"
                    f"• <b>المعرف:</b> <code>{user_id}</code>\n"
                    f"• <b>اليوزر:</b> @{safe_html(message.from_user.username or 'بدون')}\n"
                    f"• <b>الاسم:</b> {safe_html(message.from_user.first_name or '')}"
                )
                bot.send_message(admin, caption, parse_mode="HTML")
            except:
                pass
    
    # 5. بناء قائمة الأزرار (الدول والكومبوهات)
    markup = types.InlineKeyboardMarkup(row_width=2)
    buttons = []
    user_data = get_user(user_id)
    private_combo = user_data[7] if user_data else None
    all_combos = get_all_combos()

    # تجميع الكومبوهات لكل دولة
    country_combos = {}
    for country_code, combo_index in all_combos:
        if country_code not in country_combos:
            country_combos[country_code] = []
        country_combos[country_code].append(combo_index)

    # الكومبو الخاص أولاً
    if private_combo:
        c_info = COUNTRY_CODES.get(private_combo)
        name, flag, _ = c_info if c_info else ("Special", "⭐", "PV")
        svc = get_combo_service(private_combo, 1, user_id)
        app_badge = get_app_badge(svc)
        app_prefix = f"{app_badge} " if app_badge else ""
        buttons.append(types.InlineKeyboardButton(f"{flag} {app_prefix}{name} (Private)", callback_data=f"country_{private_combo}_1", style='success'))

    # عمل أزرار لكل كومبو
    for country_code, indices in country_combos.items():
        if country_code != private_combo:
            c_info = COUNTRY_CODES.get(country_code)
            if not c_info:
                _, name, flag, _ = get_country_details_smart(country_code)
            else:
                name, flag, _ = c_info

            for idx in indices:
                svc = get_combo_service(country_code, idx)
                app_badge = get_app_badge(svc)
                app_prefix = f"{app_badge} " if app_badge else ""
                if len(indices) == 1:
                    btn_text = f"{flag} {app_prefix}{name}"
                else:
                    btn_text = f"{flag} {app_prefix}{name} ({idx})"
                buttons.append(types.InlineKeyboardButton(btn_text, callback_data=f"country_{country_code}_{idx}", style='primary'))

    for i in range(0, len(buttons), 2):
        markup.row(*buttons[i:i+2])

    # زر اللغة لجميع المستخدمين
    markup.add(types.InlineKeyboardButton(get_text("btn_language", lang), callback_data="change_language", style='primary'))

    # زر لوحة التحكم للأدمن فقط
    if is_admin(user_id):
        markup.add(types.InlineKeyboardButton("🔐 Admin Panel", callback_data="admin_panel", style='danger'))

    # 6. الرسالة الترحيبية المنسقة الاحترافية بحسب لغة المستخدم
    fancy_text = get_text("welcome_banner", lang)

    bot.send_message(
        chat_id, 
        fancy_text, 
        parse_mode="HTML", 
        reply_markup=markup,
        disable_web_page_preview=True
    )

@bot.callback_query_handler(func=lambda call: call.data == "check_sub")
def check_subscription(call):
    lang = get_user_language(call.from_user.id)
    if force_sub_check(call.from_user.id):
        bot.answer_callback_query(call.id, get_text("sub_checked_ok", lang), show_alert=True)
        send_welcome(call.message)
    else:
        bot.answer_callback_query(call.id, get_text("sub_checked_fail", lang), show_alert=True)

@bot.callback_query_handler(func=lambda call: call.data.startswith("country_"))
def handle_country_selection(call):
    try:
        user_id = call.from_user.id
        chat_id = call.message.chat.id
        message_id = call.message.message_id
        lang = get_user_language(user_id)

        # 1. الفحوصات الأمنية (حظر واشتراك)
        if is_banned(user_id):
            bot.answer_callback_query(call.id, get_text("banned_user", lang), show_alert=True)
            return
        if not force_sub_check(user_id):
            bot.answer_callback_query(call.id)
            markup = force_sub_markup()
            bot.send_message(chat_id, get_text("force_sub_alert", lang), parse_mode="HTML", reply_markup=markup)
            return

        # 2. استخراج الدولة وcombo_index
        parts = call.data.split("_")
        country_code = parts[1]
        combo_index = int(parts[2]) if len(parts) > 2 else 1
        
        available_numbers = get_available_numbers(country_code, combo_index, user_id)
        
        if not available_numbers:
            bot.answer_callback_query(call.id)
            error_msg = get_text("all_numbers_busy", lang)
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton(get_text("btn_back", lang), callback_data="back_to_countries", style="danger"))
            bot.edit_message_text(error_msg, chat_id, message_id, reply_markup=markup, parse_mode="HTML")
            return

        # 3. تخصيص الرقم وتحرير القديم
        assigned = random.choice(available_numbers)
        old_user = get_user(user_id)
        if old_user and old_user[5]:
            release_number(old_user[5])
        
        assign_number_to_user(user_id, assigned)
        save_user(user_id, country_code=country_code, assigned_number=assigned)
        
        # 4. جلب بيانات الدولة وتنسيق النص
        c_info = COUNTRY_CODES.get(country_code)
        if not c_info:
            _, name, flag, short = get_country_details_smart(country_code)
        else:
            name, flag, short = c_info

        svc = get_combo_service(country_code, combo_index, user_id)
        service_display = get_service_display(svc)

        msg_text = get_text(
            "number_details",
            lang,
            number=assigned,
            country=name,
            flag=flag,
            short=short,
            combo=combo_index,
            service=service_display
        )

        # 5. بناء لوحة الأزرار
        markup = types.InlineKeyboardMarkup()
        markup.row(
            types.InlineKeyboardButton(get_text("btn_change_num", lang), callback_data=f"change_num_{country_code}_{combo_index}", style='success'),
            types.InlineKeyboardButton(get_text("btn_back", lang), callback_data="back_to_countries", style='danger')
        )

        # 6. التحديث النهائي للرسالة
        try:
            bot.edit_message_text(
                text=msg_text,
                chat_id=chat_id,
                message_id=message_id,
                reply_markup=markup,
                parse_mode="HTML",
                disable_web_page_preview=True
            )
            bot.answer_callback_query(call.id, get_text("number_assigned_alert", lang))
        except Exception as e:
            bot.answer_callback_query(call.id)
            print(f"Edit message error: {e}")
    except Exception as err:
        import traceback
        traceback.print_exc()
        try:
            bot.answer_callback_query(call.id, f"❌ حدث خطأ: {err}", show_alert=True)
        except Exception:
            pass

@bot.callback_query_handler(func=lambda call: call.data.startswith("change_num_"))
def change_number(call):
    user_id = call.from_user.id
    lang = get_user_language(user_id)
    
    # 1. الفحوصات الأمنية
    if is_banned(user_id):
        return
    if not force_sub_check(user_id):
        return
        
    # 2. استخراج كود الدولة وcombo_index
    parts = call.data.split("_")
    country_code = parts[2]
    combo_index = int(parts[3]) if len(parts) > 3 else 1
    
    available_numbers = get_available_numbers(country_code, combo_index, user_id)
    
    if not available_numbers:
        bot.answer_callback_query(call.id, get_text("all_numbers_busy", lang), show_alert=True)
        return

    # 3. تحرير الرقم القديم وتعيين الجديد
    old_user = get_user(user_id)
    if old_user and old_user[5]:
        release_number(old_user[5])
        
    assigned = random.choice(available_numbers)
    assign_number_to_user(user_id, assigned)
    save_user(user_id, assigned_number=assigned)
    
    # 4. جلب بيانات الدولة والتنسيق
    c_info = COUNTRY_CODES.get(country_code)
    if not c_info:
        _, name, flag, short = get_country_details_smart(country_code)
    else:
        name, flag, short = c_info

    svc = get_combo_service(country_code, combo_index, user_id)
    service_display = get_service_display(svc)

    msg_text = get_text(
        "number_details",
        lang,
        number=assigned,
        country=name,
        flag=flag,
        short=short,
        combo=combo_index,
        service=service_display
    )

    # 5. بناء الأزرار المحدثة
    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton(get_text("btn_change_num", lang), callback_data=f"change_num_{country_code}_{combo_index}", style='success'),
        types.InlineKeyboardButton(get_text("btn_back", lang), callback_data="back_to_countries", style='danger')
    )

    # 6. تحديث الرسالة
    try:
        bot.edit_message_text(
            text=msg_text,
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=markup,
            parse_mode="HTML",
            disable_web_page_preview=True
        )
        bot.answer_callback_query(call.id, get_text("number_changed_alert", lang))
    except Exception as e:
        print(f"Error in change_number: {e}")
        bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data == "back_to_countries")
def back_to_countries(call):
    lang = get_user_language(call.from_user.id)
    # 1. بناء قائمة الأزرار
    markup = types.InlineKeyboardMarkup(row_width=2)
    buttons = []
    
    # جلب البيانات
    user = get_user(call.from_user.id)
    private_combo = user[7] if user else None
    all_combos = get_all_combos()

    # تجميع الكومبوهات لكل دولة
    country_combos = {}
    for country_code, combo_index in all_combos:
        if country_code not in country_combos:
            country_combos[country_code] = []
        country_combos[country_code].append(combo_index)

    # إضافة الكومبو الخاص أولاً (إذا وُجد)
    if private_combo:
        c_info = COUNTRY_CODES.get(private_combo)
        name, flag, _ = c_info if c_info else ("Special", "⭐", "PV")
        svc = get_combo_service(private_combo, 1, call.from_user.id)
        app_badge = get_app_badge(svc)
        app_prefix = f"{app_badge} " if app_badge else ""
        buttons.append(types.InlineKeyboardButton(f"{flag} {app_prefix}{name} (Private)", callback_data=f"country_{private_combo}_1", style='success'))

    # إضافة الكومبوهات العامة
    for country_code, indices in country_combos.items():
        if country_code != private_combo:
            c_info = COUNTRY_CODES.get(country_code)
            if not c_info:
                _, name, flag, _ = get_country_details_smart(country_code)
            else:
                name, flag, _ = c_info

            for idx in indices:
                svc = get_combo_service(country_code, idx)
                app_badge = get_app_badge(svc)
                app_prefix = f"{app_badge} " if app_badge else ""
                if len(indices) == 1:
                    btn_text = f"{flag} {app_prefix}{name}"
                else:
                    btn_text = f"{flag} {app_prefix}{name} ({idx})"
                buttons.append(types.InlineKeyboardButton(btn_text, callback_data=f"country_{country_code}_{idx}", style='primary'))

    # توزيع الأزرار في صفوف
    for i in range(0, len(buttons), 2):
        markup.row(*buttons[i:i+2])

    # زر اللغة لجميع المستخدمين
    markup.add(types.InlineKeyboardButton(get_text("btn_language", lang), callback_data="change_language", style='primary'))

    # إضافة زر الإدارة للمشرفين
    if is_admin(call.from_user.id):
        admin_btn = types.InlineKeyboardButton("🔐 Admin Panel", callback_data="admin_panel", style='danger')
        markup.add(admin_btn)

    # 2. النص المنسق الاحترافي بحسب لغة المستخدم
    fancy_text = get_text("welcome_banner", lang)

    # 3. تعديل الرسالة الحالية
    try:
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=fancy_text,
            parse_mode="HTML",
            reply_markup=markup,
            disable_web_page_preview=True
        )
    except Exception as e:
        print(f"Error editing message: {e}")
        bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data == "change_language")
def handle_change_language_menu(call):
    lang = get_user_language(call.from_user.id)
    prompt = get_text("choose_language", lang)
    markup = build_language_markup(lang)
    try:
        bot.edit_message_text(
            text=prompt,
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=markup,
            parse_mode="HTML"
        )
    except Exception:
        bot.send_message(call.message.chat.id, prompt, reply_markup=markup, parse_mode="HTML")
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data.startswith("set_lang_"))
def handle_set_language_callback(call):
    new_lang = call.data.split("_", 2)[2]
    if new_lang in SUPPORTED_LANGUAGES:
        set_user_language(call.from_user.id, new_lang)
        alert_text = get_text("language_changed", new_lang)
        bot.answer_callback_query(call.id, alert_text, show_alert=True)
        back_to_countries(call)
    else:
        bot.answer_callback_query(call.id)


# ======================
# 🔐 لوحة التحكم الإدارية (محدثة)
# ======================
user_states = {}

def admin_main_menu(lang='ar'):
    markup = types.InlineKeyboardMarkup()
    
    # 1. زر حالة البوت (يحتل الصدارة)
    status_icon = "🟢" if not is_maintenance_mode() else "🔴"
    status_text = get_text("admin_status_online", lang) if not is_maintenance_mode() else get_text("admin_status_maint", lang)
    status_style = 'success' if not is_maintenance_mode() else 'danger'
    markup.add(types.InlineKeyboardButton(f"{status_icon} {status_text} {status_icon}", callback_data="toggle_maintenance", style=status_style))
    
    # 2. قسم إدارة الكومبوهات (أزرار كبيرة)
    markup.row(
        types.InlineKeyboardButton(get_text("admin_add_combo", lang), callback_data="admin_add_combo", style='success'),
        types.InlineKeyboardButton(get_text("admin_del_combo", lang), callback_data="admin_del_combo", style='danger')
    )
    markup.add(
        types.InlineKeyboardButton("🏷️ تخصيص تطبيق لكومبو (WhatsApp / TikTok..)", callback_data="admin_combo_service_menu", style='primary')
    )
    
    # 3. قسم الإحصائيات والتقارير
    markup.row(
        types.InlineKeyboardButton(get_text("admin_stats", lang), callback_data="admin_stats", style='primary'),
        types.InlineKeyboardButton(get_text("admin_full_report", lang), callback_data="admin_full_report", style='primary')
    )
    
    # 4. قسم الإذاعة (Broadcast)
    markup.row(
        types.InlineKeyboardButton(get_text("admin_broadcast_all", lang), callback_data="admin_broadcast_all", style='primary'),
        types.InlineKeyboardButton(get_text("admin_broadcast_user", lang), callback_data="admin_broadcast_user", style='primary')
    )
    
    # 5. قسم إدارة المستخدمين
    markup.row(
        types.InlineKeyboardButton(get_text("admin_ban", lang), callback_data="admin_ban", style='danger'),
        types.InlineKeyboardButton(get_text("admin_unban", lang), callback_data="admin_unban", style='success'),
        types.InlineKeyboardButton(get_text("admin_user_info", lang), callback_data="admin_user_info", style='primary')
    )
    
    # 6. قسم الإعدادات المتقدمة
    markup.row(
        types.InlineKeyboardButton(get_text("admin_force_sub", lang), callback_data="admin_force_sub", style='primary'),
        types.InlineKeyboardButton(get_text("admin_dashboards", lang), callback_data="admin_dashboards", style='primary'),
        types.InlineKeyboardButton(get_text("admin_private_combo", lang), callback_data="admin_private_combo", style='primary')
    )

    # 7. قسم إدارة الأرقام وفحص الكوكيز (iVasms)
    markup.row(
        types.InlineKeyboardButton(get_text("admin_ivasms_panel", lang), callback_data="admin_ivasms_panel", style='primary'),
        types.InlineKeyboardButton(get_text("admin_cookies_panel", lang), callback_data="admin_cookies_panel", style='primary')
    )

    # 8. قسم إدارة الأدمنية
    markup.row(
        types.InlineKeyboardButton(get_text("admin_manage_admins", lang), callback_data="admin_manage_admins", style='primary')
    )

    # 9. زر تغيير لغة لوحة الإدارة
    markup.add(types.InlineKeyboardButton(get_text("admin_change_lang", lang), callback_data="admin_change_lang", style='primary'))

    # 10. زر الخروج
    markup.add(types.InlineKeyboardButton(get_text("admin_leave", lang), callback_data="back_to_countries", style='danger'))
    
    return markup

@bot.message_handler(commands=['admin'])
def cmd_admin(message):
    lang = get_user_language(message.from_user.id)
    if not is_admin(message.from_user.id):
        bot.reply_to(message, get_text("admin_only_alert", lang))
        return
    status_str = f"{get_text('admin_status_online', lang)} 🟢" if not is_maintenance_mode() else f"{get_text('admin_status_maint', lang)} 🔴"
    admin_text = (
        f"🛡️ <b>{get_text('admin_title', lang)}</b>\n\n"
        f"<b>👋 {get_text('admin_greeting', lang)}</b>\n\n" 
        f"<b>⚙️ {get_text('admin_desc', lang)}</b>\n"
        f"<b>⚠️ {get_text('admin_warning', lang)}</b>\n\n"
        f"📊 <b>{get_text('admin_sys_info', lang)}:</b>\n"
        f"• <b>{get_text('admin_bot_status', lang)}:</b> {status_str}\n"
        f"• <b>{get_text('admin_server_conn', lang)}:</b> <u>{get_text('admin_online_label', lang)}</u> ✅\n"
        f"• <b>{get_text('admin_current_time', lang)}:</b> <code>{datetime.now().strftime('%H:%M - %Y/%m/%d')}</code>"
    )
    try:
        bot.send_message(
            message.chat.id,
            admin_text,
            parse_mode="HTML",
            reply_markup=admin_main_menu(lang),
            disable_web_page_preview=True
        )
    except Exception as e:
        print(f"Admin Command Error: {e}")

@bot.callback_query_handler(func=lambda call: call.data == "admin_panel")
def show_admin_panel(call):
    lang = get_user_language(call.from_user.id)
    # التحقق من الرتبة أولاً
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, get_text("admin_only_alert", lang), show_alert=True)
        return

    status_str = f"{get_text('admin_status_online', lang)} 🟢" if not is_maintenance_mode() else f"{get_text('admin_status_maint', lang)} 🔴"
    admin_text = (
        f"🛡️ <b>{get_text('admin_title', lang)}</b>\n\n"
        f"<b>👋 {get_text('admin_greeting', lang)}</b>\n\n" 
        f"<b>⚙️ {get_text('admin_desc', lang)}</b>\n"
        f"<b>⚠️ {get_text('admin_warning', lang)}</b>\n\n"
        f"📊 <b>{get_text('admin_sys_info', lang)}:</b>\n"
        f"• <b>{get_text('admin_bot_status', lang)}:</b> {status_str}\n"
        f"• <b>{get_text('admin_server_conn', lang)}:</b> <u>{get_text('admin_online_label', lang)}</u> ✅\n"
        f"• <b>{get_text('admin_current_time', lang)}:</b> <code>{datetime.now().strftime('%H:%M - %Y/%m/%d')}</code>"
    )
    
    try:
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=admin_text,
            parse_mode="HTML",
            reply_markup=admin_main_menu(lang),
            disable_web_page_preview=True
        )
    except Exception as e:
        print(f"Admin Panel Error: {e}")

@bot.callback_query_handler(func=lambda call: call.data == "admin_change_lang")
def handle_admin_change_lang_menu(call):
    if not is_admin(call.from_user.id):
        return
    lang = get_user_language(call.from_user.id)
    prompt = get_text("choose_admin_lang", lang)
    markup = build_admin_language_markup(lang)
    try:
        bot.edit_message_text(
            text=prompt,
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=markup,
            parse_mode="HTML"
        )
    except Exception:
        bot.send_message(call.message.chat.id, prompt, reply_markup=markup, parse_mode="HTML")
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data.startswith("set_admin_lang_"))
def handle_set_admin_lang_callback(call):
    if not is_admin(call.from_user.id):
        return
    new_lang = call.data.split("_", 3)[3]
    if new_lang in SUPPORTED_LANGUAGES:
        set_user_language(call.from_user.id, new_lang)
        alert_text = get_text("admin_lang_changed", new_lang)
        bot.answer_callback_query(call.id, alert_text, show_alert=True)
        show_admin_panel(call)
    else:
        bot.answer_callback_query(call.id)

# ======================
# 👮‍♂️ إدارة الأدمنية من لوحة التحكم
# ======================
def build_admin_manage_markup(lang='ar'):
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.row(
        types.InlineKeyboardButton(get_text("admin_add_admin", lang), callback_data="admin_add_admin", style='success'),
        types.InlineKeyboardButton(get_text("admin_del_admin", lang), callback_data="admin_del_admin", style='danger')
    )
    markup.row(
        types.InlineKeyboardButton(get_text("admin_list_admins", lang), callback_data="admin_list_admins", style='primary')
    )
    markup.row(
        types.InlineKeyboardButton(get_text("admin_btn_back", lang), callback_data="admin_panel", style='danger')
    )
    return markup

@bot.callback_query_handler(func=lambda call: call.data == "admin_manage_admins")
def handle_admin_manage_admins(call):
    if not is_admin(call.from_user.id):
        return
    lang = get_user_language(call.from_user.id)
    admins_count = len(get_all_admins())
    text = (
        f"{get_text('admin_panel_admins_title', lang)}\n\n"
        f"• <b>{get_text('admin_stats', lang)}:</b> <code>{admins_count}</code>"
    )
    markup = build_admin_manage_markup(lang)
    try:
        bot.edit_message_text(text, chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=markup, parse_mode="HTML")
    except Exception:
        bot.send_message(call.message.chat.id, text, reply_markup=markup, parse_mode="HTML")
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data == "admin_add_admin")
def handle_admin_add_admin(call):
    if not is_admin(call.from_user.id):
        return
    lang = get_user_language(call.from_user.id)
    chat_id = call.message.chat.id
    user_states[chat_id] = "add_admin"
    
    mar = types.InlineKeyboardMarkup([[
        types.InlineKeyboardButton(get_text("btn_back", lang), callback_data="admin_manage_admins", style='danger')
    ]])
    prompt_text = get_text("admin_prompt_send_id", lang)
    try:
        bot.edit_message_text(prompt_text, chat_id=chat_id, message_id=call.message.message_id, reply_markup=mar, parse_mode="HTML")
    except Exception:
        bot.send_message(chat_id, prompt_text, reply_markup=mar, parse_mode="HTML")
    bot.answer_callback_query(call.id)

@bot.message_handler(func=lambda msg: user_states.get(msg.from_user.id) == "add_admin")
def process_add_admin_msg(message):
    lang = get_user_language(message.from_user.id)
    if not is_admin(message.from_user.id):
        return
    
    target_id = None
    if message.forward_from:
        target_id = message.forward_from.id
    else:
        text = message.text.strip() if message.text else ""
        if text.isdigit():
            target_id = int(text)

    if not target_id:
        bot.reply_to(message, get_text("invalid_user_id", lang))
        return

    if target_id in get_all_admins():
        bot.reply_to(message, get_text("admin_already_exists", lang))
        user_states.pop(message.from_user.id, None)
        return

    success = add_admin_db(target_id, added_by=message.from_user.id)
    if success:
        user_states.pop(message.from_user.id, None)
        bot.reply_to(
            message,
            get_text("admin_added_success", lang, admin_id=target_id),
            parse_mode="HTML"
        )
        try:
            target_lang = get_user_language(target_id)
            bot.send_message(
                target_id,
                get_text("admin_notify_promoted", target_lang),
                parse_mode="HTML"
            )
        except Exception:
            pass
    else:
        bot.reply_to(message, "❌ حدث خطأ أثناء إضافة الأدمن إلى قاعدة البيانات.")

@bot.callback_query_handler(func=lambda call: call.data == "admin_list_admins")
def handle_admin_list_admins(call):
    if not is_admin(call.from_user.id):
        return
    lang = get_user_language(call.from_user.id)
    details = get_admins_details()
    
    text = get_text("admin_list_title", lang)
    for idx, adm in enumerate(details, 1):
        uid = adm['user_id']
        badge = get_text("admin_owner_badge", lang) if adm['is_owner'] else get_text("admin_role_badge", lang)
        date_info = f" ({adm['added_at']})" if not adm['is_owner'] else ""
        text += f"{idx}. <code>{uid}</code> {badge}{date_info}\n"
        
    mar = types.InlineKeyboardMarkup(row_width=1)
    mar.add(
        types.InlineKeyboardButton(get_text("admin_add_admin", lang), callback_data="admin_add_admin", style='success'),
        types.InlineKeyboardButton(get_text("admin_del_admin", lang), callback_data="admin_del_admin", style='danger'),
        types.InlineKeyboardButton(get_text("btn_back", lang), callback_data="admin_manage_admins", style='danger')
    )
    try:
        bot.edit_message_text(text, chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=mar, parse_mode="HTML")
    except Exception:
        bot.send_message(call.message.chat.id, text, reply_markup=mar, parse_mode="HTML")
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data == "admin_del_admin")
def handle_admin_del_admin(call):
    if not is_admin(call.from_user.id):
        return
    lang = get_user_language(call.from_user.id)
    details = [a for a in get_admins_details() if not a['is_owner']]
    
    if not details:
        text = get_text("admin_no_removable_admins", lang)
        mar = types.InlineKeyboardMarkup([[
            types.InlineKeyboardButton(get_text("btn_back", lang), callback_data="admin_manage_admins", style='danger')
        ]])
    else:
        text = get_text("admin_del_select_prompt", lang)
        mar = types.InlineKeyboardMarkup(row_width=1)
        for adm in details:
            uid = adm['user_id']
            mar.add(types.InlineKeyboardButton(f"🗑️ {uid}", callback_data=f"del_admin_id_{uid}", style='danger'))
        mar.add(types.InlineKeyboardButton(get_text("btn_back", lang), callback_data="admin_manage_admins", style='danger'))
        
    try:
        bot.edit_message_text(text, chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=mar, parse_mode="HTML")
    except Exception:
        bot.send_message(call.message.chat.id, text, reply_markup=mar, parse_mode="HTML")
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data.startswith("del_admin_id_"))
def handle_do_del_admin(call):
    if not is_admin(call.from_user.id):
        return
    lang = get_user_language(call.from_user.id)
    try:
        target_id = int(call.data.split("_")[3])
    except Exception:
        bot.answer_callback_query(call.id, "Error", show_alert=True)
        return
        
    success, reason = remove_admin_db(target_id)
    if success:
        bot.answer_callback_query(call.id, get_text("admin_removed_success", lang, admin_id=target_id), show_alert=True)
        handle_admin_del_admin(call)
    else:
        if reason == "owner":
            bot.answer_callback_query(call.id, get_text("admin_cannot_remove_owner", lang), show_alert=True)
        else:
            bot.answer_callback_query(call.id, f"Error: {reason}", show_alert=True)

# ======================
# 📌 ميزة الاشتراك الإجباري في لوحة الإدارة
# ======================
@bot.callback_query_handler(func=lambda call: call.data == "admin_force_sub")
def admin_force_sub(call):
    if not is_admin(call.from_user.id):
        return

    channels = get_all_force_sub_channels(enabled_only=False)
    text = "⚙️ إدارة قنوات الاشتراك الإجباري:\n"
    text += f"إجمالي القنوات: {len(channels)}\n\n"

    markup = types.InlineKeyboardMarkup()
    for ch_id, url, desc in channels:
        # جلب الحالة بدقة
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT enabled FROM force_sub_channels WHERE id=?", (ch_id,))
        enabled = c.fetchone()[0]
        conn.close()
        status = "✅" if enabled else "❌"
        btn_text = f"{status} {desc or url[:25]}"
        markup.add(types.InlineKeyboardButton(btn_text, callback_data=f"edit_force_ch_{ch_id}", style='primary'))

    markup.add(types.InlineKeyboardButton("➕ إضافة قناة", callback_data="add_force_ch", style='success'))
    markup.add(types.InlineKeyboardButton("🔙 Back", callback_data="admin_panel", style='danger'))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "toggle_maintenance")
def handle_maintenance_toggle(call):
    if not is_admin(call.from_user.id): return
    
    # عكس الحالة الحالية
    current_status = is_maintenance_mode()
    set_maintenance_mode(not current_status) # دالة الحفظ
    
    new_status_text = "🔓 تم فتح البوت للجميع" if current_status else "🔒 تم قفل البوت (وضع الصيانة)"
    
    # إشعار سريع للأدمن
    bot.answer_callback_query(call.id, new_status_text, show_alert=True)
    
    # تحديث اللوحة فوراً ليتغير شكل الزر
    bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=admin_main_menu())
    
# --- إضافة قناة جديدة ---
@bot.callback_query_handler(func=lambda call: call.data == "add_force_ch")
def add_force_ch_step1(call):
    if not is_admin(call.from_user.id):
        return
    user_states[call.from_user.id] = "add_force_ch_url"
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔙 Back", callback_data="admin_force_sub", style='danger'))
    bot.edit_message_text("أرسل رابط القناة (مثل: https://t.me/xxx أو @xxx):", call.message.chat.id, call.message.message_id, reply_markup=markup)

@bot.message_handler(func=lambda msg: user_states.get(msg.from_user.id) == "add_force_ch_url")
def add_force_ch_step2(message):
    url = message.text.strip()
    if not (url.startswith("@") or url.startswith("https://t.me/")):
        bot.reply_to(message, "❌ رابط غير صالح! يجب أن يبدأ بـ @ أو https://t.me/")
        return
    user_states[message.from_user.id] = {"step": "add_force_ch_desc", "url": url}
    bot.reply_to(message, "أدخل وصفًا للقناة (أو اترك فارغًا):")

@bot.message_handler(func=lambda msg: isinstance(user_states.get(msg.from_user.id), dict) and user_states[msg.from_user.id].get("step") == "add_force_ch_desc")
def add_force_ch_step3(message):
    data = user_states[message.from_user.id]
    url = data["url"]
    desc = message.text.strip()
    if add_force_sub_channel(url, desc):
        bot.reply_to(message, f"✅ تم إضافة القناة:\n{url}\nالوصف: {desc or '—'}")
    else:
        bot.reply_to(message, "❌ القناة موجودة مسبقًا!")
    del user_states[message.from_user.id]

# --- تعديل/حذف قناة فردية ---
@bot.callback_query_handler(func=lambda call: call.data.startswith("edit_force_ch_"))
def edit_force_ch(call):
    if not is_admin(call.from_user.id):
        return
    try:
        ch_id = int(call.data.split("_", 3)[3])
    except:
        return
    # جلب بيانات القناة
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT channel_url, description, enabled FROM force_sub_channels WHERE id=?", (ch_id,))
    row = c.fetchone()
    conn.close()
    if not row:
        bot.answer_callback_query(call.id, "❌ القناة غير موجودة!", show_alert=True)
        return

    url, desc, enabled = row
    status = "مفعلة" if enabled else "معطلة"
    text = f"🔧 إدارة القناة:\nالرابط: {url}\nالوصف: {desc or '—'}\nالحالة: {status}"
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("✏️ تعديل الوصف", callback_data=f"edit_desc_{ch_id}", style='primary'))
    if enabled:
        markup.add(types.InlineKeyboardButton("❌ تعطيل", callback_data=f"toggle_ch_{ch_id}", style='danger'))
    else:
        markup.add(types.InlineKeyboardButton("✅ تفعيل", callback_data=f"toggle_ch_{ch_id}", style='success'))
    markup.add(types.InlineKeyboardButton("🗑️ حذف", callback_data=f"del_ch_{ch_id}", style='danger'))
    markup.add(types.InlineKeyboardButton("🔙 Back", callback_data="admin_force_sub", style='danger'))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("toggle_ch_"))
def toggle_ch(call):
    ch_id = int(call.data.split("_", 2)[2])
    toggle_force_sub_channel(ch_id)
    bot.answer_callback_query(call.id, "🔄 تم تغيير حالة القناة", show_alert=True)
    admin_force_sub(call)

@bot.callback_query_handler(func=lambda call: call.data.startswith("del_ch_"))
def del_ch(call):
    ch_id = int(call.data.split("_", 2)[2])
    if delete_force_sub_channel(ch_id):
        bot.answer_callback_query(call.id, "✅ تم الحذف!", show_alert=True)
    else:
        bot.answer_callback_query(call.id, "❌ فشل الحذف!", show_alert=True)
    admin_force_sub(call)

@bot.callback_query_handler(func=lambda call: call.data.startswith("edit_desc_"))
def edit_desc_step1(call):
    ch_id = int(call.data.split("_", 2)[2])
    user_states[call.from_user.id] = f"edit_desc_{ch_id}"
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔙 Back", callback_data=f"edit_force_ch_{ch_id}", style='danger'))
    bot.edit_message_text("أدخل الوصف الجديد:", call.message.chat.id, call.message.message_id, reply_markup=markup)

@bot.message_handler(func=lambda msg: isinstance(user_states.get(msg.from_user.id), str) and user_states[msg.from_user.id].startswith("edit_desc_"))
def edit_desc_step2(message):
    try:
        ch_id = int(user_states[message.from_user.id].split("_")[2])
        desc = message.text.strip()
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("UPDATE force_sub_channels SET description = ? WHERE id = ?", (desc, ch_id))
        conn.commit()
        conn.close()
        bot.reply_to(message, "✅ تم تحديث الوصف!")
    except Exception as e:
        bot.reply_to(message, f"❌ خطأ: {e}")
    del user_states[message.from_user.id]

@bot.callback_query_handler(func=lambda call: call.data == "admin_add_combo")
def admin_add_combo(call):
    if not is_admin(call.from_user.id):
        return
    user_states[call.from_user.id] = "waiting_combo_file"
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔙 Back", callback_data="admin_panel", style='danger'))
    bot.edit_message_text("📤 أرسل ملف الكومبو بصيغة TXT", call.message.chat.id, call.message.message_id, reply_markup=markup)

@bot.message_handler(content_types=['document'])
def handle_combo_file(message):
    if not is_admin(message.from_user.id):
        return
    if user_states.get(message.from_user.id) != "waiting_combo_file":
        return
    try:
        file_info = bot.get_file(message.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        content = downloaded_file.decode('utf-8')
        lines = [line.strip() for line in content.splitlines() if line.strip()]
        if not lines:
            bot.reply_to(message, "❌ الملف فارغ!")
            return
        first_num = clean_number(lines[0])
        country_code = None
        for code in COUNTRY_CODES:
            if first_num.startswith(code):
                country_code = code
                break
        if not country_code:
            bot.reply_to(message, "❌ لا يمكن تحديد الدولة من الأرقام!")
            return
        save_combo(country_code, lines)
        name, flag, _ = COUNTRY_CODES[country_code]
        bot.reply_to(message, f"✅ تم حفظ الكومبو لدولة {flag} {name}\n🔢 عدد الأرقام: {len(lines)}")
        del user_states[message.from_user.id]
    except Exception as e:
        bot.reply_to(message, f"❌ خطأ: {e}")

@bot.callback_query_handler(func=lambda call: call.data == "admin_del_combo")
def admin_del_combo(call):
    if not is_admin(call.from_user.id):
        return
    combos = get_all_combos()
    if not combos:
        bot.answer_callback_query(call.id, "لا توجد كومبوهات!")
        return
    markup = types.InlineKeyboardMarkup()
    # تجميع الكومبوهات لكل دولة
    country_combos = {}
    for country_code, combo_index in combos:
        if country_code not in country_combos:
            country_combos[country_code] = []
        country_combos[country_code].append(combo_index)
    
    for country_code, indices in country_combos.items():
        if country_code in COUNTRY_CODES:
            name, flag, _ = COUNTRY_CODES[country_code]
            for idx in indices:
                # إذا كان الكومبو الأول فقط أو دولة واحدة فقط، ما نضيف رقم
                if len(indices) == 1:
                    btn_text = f"{flag} {name}"
                else:
                    btn_text = f"{flag} {name} ({idx})"
                markup.add(types.InlineKeyboardButton(btn_text, callback_data=f"del_combo_{country_code}_{idx}", style='primary'))
    
    markup.add(types.InlineKeyboardButton("🔙 Back", callback_data="admin_panel", style='danger'))
    bot.edit_message_text("اختر الكومبو للحذف:", call.message.chat.id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("del_combo_"))
def confirm_del_combo(call):
    if not is_admin(call.from_user.id):
        return
    
    parts = call.data.split("_")
    country_code = parts[2]
    combo_index = int(parts[3]) if len(parts) > 3 else 1
    
    # استدعاء الدالة المعدلة
    success = delete_combo(country_code, combo_index)
    
    name, flag, _ = COUNTRY_CODES.get(country_code, ("Unknown", "🌍", ""))
    
    if success:
        bot.answer_callback_query(call.id, f"✅ تم حذف الكومبو: {flag} {name} ({combo_index})", show_alert=True)
    else:
        bot.answer_callback_query(call.id, f"❌ فشل حذف الكومبو!", show_alert=True)
    
    # تحديث القائمة
    admin_del_combo(call)

@bot.callback_query_handler(func=lambda call: call.data == "admin_stats")
def admin_stats(call):
    if not is_admin(call.from_user.id):
        return
    total_users = len(get_all_users())
    combos = get_all_combos()
    
    # حساب عدد الكومبوهات الفريدة
    unique_countries = set()
    total_combos = 0
    for country_code, combo_index in combos:
        unique_countries.add(country_code)
        total_combos += 1
    
    total_numbers = 0
    for country_code, combo_index in combos:
        total_numbers += len(get_combo(country_code, combo_index))
    
    otp_count = len(get_otp_logs())
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔙 Back", callback_data="admin_panel", style='danger'))
    bot.edit_message_text(
        f"📊 إحصائيات البوت:\n"
        f"👥 المستخدمين النشطين: {total_users}\n"
        f"🌐 الدول المضافة: {len(unique_countries)}\n"
        f"📦 الكومبوهات: {total_combos}\n"
        f"📞 إجمالي الأرقام: {total_numbers}\n"
        f"🔑 إجمالي الأكواد المستلمة: {otp_count}",
        call.message.chat.id, call.message.message_id, reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data == "admin_full_report")
def admin_full_report(call):
    if not is_admin(call.from_user.id):
        return
    try:
        report = "📊 تقرير شامل عن البوت\n" + "="*40 + "\n\n"
        # المستخدمون
        report += "👥 المستخدمون:\n"
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT * FROM users")
        users = c.fetchall()
        for u in users:
            status = "محظور" if u[6] else "نشط"
            report += f"ID: {u[0]} | @{u[1] or 'N/A'} | الرقم: {u[5] or 'N/A'} | الحالة: {status}\n"
        report += "\n" + "="*40 + "\n\n"
        # الأكواد
        report += "🔑 سجل الأكواد:\n"
        c.execute("SELECT * FROM otp_logs")
        logs = c.fetchall()
        for log in logs:
            user_info = get_user_info(log[5]) if log[5] else None
            user_tag = f"@{user_info[1]}" if user_info and user_info[1] else f"ID:{log[5] or 'N/A'}"
            report += f"الرقم: {log[1]} | الكود: {log[2]} | المستخدم: {user_tag} | الوقت: {log[4]}\n"
        
        # الكومبوهات
        report += "\n" + "="*40 + "\n\n"
        report += "📦 الكومبوهات:\n"
        c.execute("SELECT country_code, combo_index, LENGTH(numbers) FROM combos")
        combos_data = c.fetchall()
        for country_code, combo_index, num_length in combos_data:
            name, flag, _ = COUNTRY_CODES.get(country_code, ("Unknown", "🌍", ""))
            num_count = len(get_combo(country_code, combo_index))
            report += f"{flag} {name} ({combo_index}): {num_count} رقم\n"
        
        conn.close()
        report += "\n" + "="*40 + "\n\n"
        report += "تم إنشاء التقرير في: " + datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open("bot_report.txt", "w", encoding="utf-8") as f:
            f.write(report)
        with open("bot_report.txt", "rb") as f:
            bot.send_document(call.from_user.id, f)
        os.remove("bot_report.txt")
        bot.answer_callback_query(call.id, "✅ تم إرسال التقرير!", show_alert=True)
    except Exception as e:
        bot.answer_callback_query(call.id, f"❌ خطأ: {e}", show_alert=True)

@bot.callback_query_handler(func=lambda call: call.data == "admin_ban")
def admin_ban_step1(call):
    if not is_admin(call.from_user.id):
        return
    user_states[call.from_user.id] = "ban_user"
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔙 Back", callback_data="admin_panel", style='danger'))
    bot.edit_message_text("أدخل معرف المستخدم لحظره:", call.message.chat.id, call.message.message_id, reply_markup=markup)

@bot.message_handler(func=lambda msg: user_states.get(msg.from_user.id) == "ban_user")
def admin_ban_step2(message):
    try:
        uid = int(message.text)
        ban_user(uid)
        bot.reply_to(message, f"✅ تم حظر المستخدم {uid}")
        del user_states[message.from_user.id]
    except:
        bot.reply_to(message, "❌ معرف غير صحيح!")

@bot.callback_query_handler(func=lambda call: call.data == "admin_unban")
def admin_unban_step1(call):
    if not is_admin(call.from_user.id):
        return
    user_states[call.from_user.id] = "unban_user"
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔙 Back", callback_data="admin_panel", style='danger'))
    bot.edit_message_text("أدخل معرف المستخدم لفك حظره:", call.message.chat.id, call.message.message_id, reply_markup=markup)

@bot.message_handler(func=lambda msg: user_states.get(msg.from_user.id) == "unban_user")
def admin_unban_step2(message):
    try:
        uid = int(message.text)
        unban_user(uid)
        bot.reply_to(message, f"✅ تم فك حظر المستخدم {uid}")
        del user_states[message.from_user.id]
    except:
        bot.reply_to(message, "❌ معرف غير صحيح!")

@bot.callback_query_handler(func=lambda call: call.data == "admin_broadcast_all")
def admin_broadcast_all_step1(call):
    if not is_admin(call.from_user.id):
        return
    user_states[call.from_user.id] = "broadcast_all"
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔙 Back", callback_data="admin_panel", style='danger'))
    bot.edit_message_text("أرسل الرسالة للإرسال للجميع:", call.message.chat.id, call.message.message_id, reply_markup=markup)

@bot.message_handler(func=lambda msg: user_states.get(msg.from_user.id) == "broadcast_all")
def admin_broadcast_all_step2(message):
    users = get_all_users()
    success = 0
    for uid in users:
        try:
            bot.send_message(uid, message.text)
            success += 1
        except:
            pass
    bot.reply_to(message, f"✅ تم الإرسال إلى {success}/{len(users)} مستخدم")
    del user_states[message.from_user.id]

@bot.callback_query_handler(func=lambda call: call.data == "admin_broadcast_user")
def admin_broadcast_user_step1(call):
    if not is_admin(call.from_user.id):
        return
    user_states[call.from_user.id] = "broadcast_user_id"
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔙 Back", callback_data="admin_panel", style='danger'))
    bot.edit_message_text("أدخل معرف المستخدم:", call.message.chat.id, call.message.message_id, reply_markup=markup)

@bot.message_handler(func=lambda msg: user_states.get(msg.from_user.id) == "broadcast_user_id")
def admin_broadcast_user_step2(message):
    try:
        uid = int(message.text)
        user_states[message.from_user.id] = f"broadcast_msg_{uid}"
        bot.reply_to(message, "أرسل الرسالة:")
    except:
        bot.reply_to(message, "❌ معرف غير صحيح!")

@bot.message_handler(func=lambda msg: user_states.get(msg.from_user.id, "").startswith("broadcast_msg_"))
def admin_broadcast_user_step3(message):
    uid = int(user_states[message.from_user.id].split("_")[2])
    try:
        bot.send_message(uid, message.text)
        bot.reply_to(message, f"✅ تم الإرسال للمستخدم {uid}")
    except Exception as e:
        bot.reply_to(message, f"❌ فشل: {e}")
    del user_states[message.from_user.id]

@bot.callback_query_handler(func=lambda call: call.data == "admin_user_info")
def admin_user_info_step1(call):
    if not is_admin(call.from_user.id):
        return
    user_states[call.from_user.id] = "get_user_info"
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔙 Back", callback_data="admin_panel", style='danger'))
    bot.edit_message_text("أدخل معرف المستخدم:", call.message.chat.id, call.message.message_id, reply_markup=markup)

@bot.message_handler(func=lambda msg: user_states.get(msg.from_user.id) == "get_user_info")
def admin_user_info_step2(message):
    try:
        uid = int(message.text)
        user = get_user_info(uid)
        if not user:
            bot.reply_to(message, "❌ المستخدم غير موجود!")
            return
        status = "محظور" if user[6] else "نشط"
        info = f"👤 معلومات المستخدم:\n"
        info += f"🆔: {user[0]}\n"
        info += f".Username: @{user[1] or 'N/A'}\n"
        info += f"الاسم: {user[2] or ''} {user[3] or ''}\n"
        info += f"الرقم المخصص: {user[5] or 'N/A'}\n"
        info += f"الحالة: {status}"
        bot.reply_to(message, info)
    except Exception as e:
        bot.reply_to(message, f"❌ خطأ: {e}")
    del user_states[message.from_user.id]

@bot.callback_query_handler(func=lambda call: call.data == "admin_private_combo")
def admin_private_combo(call):
    if not is_admin(call.from_user.id):
        return
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("➕ إضافة كومبو برايفت", callback_data="add_private_combo", style='success'))
    markup.add(types.InlineKeyboardButton("🗑️ مسح كومبو برايفت", callback_data="del_private_combo", style='danger'))
    markup.add(types.InlineKeyboardButton("🔙 Back", callback_data="admin_panel", style='danger'))
    bot.edit_message_text("👤 كومبو برايفت:", call.message.chat.id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "add_private_combo")
def add_private_combo_step1(call):
    if not is_admin(call.from_user.id):
        return
    user_states[call.from_user.id] = "add_private_user_id"
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔙 Back", callback_data="admin_private_combo", style='danger'))
    bot.edit_message_text("أدخل معرف المستخدم:", call.message.chat.id, call.message.message_id, reply_markup=markup)

@bot.message_handler(func=lambda msg: user_states.get(msg.from_user.id) == "add_private_user_id")
def add_private_combo_step2(message):
    try:
        uid = int(message.text)
        user_states[message.from_user.id] = f"add_private_country_{uid}"
        markup = types.InlineKeyboardMarkup(row_width=2)
        buttons = []
        # تجميع الكومبوهات لكل دولة
        all_combos = get_all_combos()
        country_combos = {}
        for country_code, combo_index in all_combos:
            if country_code not in country_combos:
                country_combos[country_code] = []
            country_combos[country_code].append(combo_index)
        
        for country_code, indices in country_combos.items():
            if country_code in COUNTRY_CODES:
                name, flag, _ = COUNTRY_CODES[country_code]
                for idx in indices:
                    if len(indices) == 1:
                        btn_text = f"{flag} {name}"
                    else:
                        btn_text = f"{flag} {name} ({idx})"
                    buttons.append(types.InlineKeyboardButton(btn_text, callback_data=f"select_private_{uid}_{country_code}", style='primary'))
        for i in range(0, len(buttons), 2):
            markup.row(*buttons[i:i+2])
        markup.add(types.InlineKeyboardButton("🔙 Back", callback_data="admin_private_combo", style='danger'))
        bot.reply_to(message, "اختر الدولة:", reply_markup=markup)
    except:
        bot.reply_to(message, "❌ معرف غير صحيح!")

@bot.callback_query_handler(func=lambda call: call.data.startswith("select_private_"))
def select_private_combo(call):
    parts = call.data.split("_")
    uid = int(parts[2])
    country_code = parts[3]
    save_user(uid, private_combo_country=country_code)
    name, flag, _ = COUNTRY_CODES[country_code]
    bot.answer_callback_query(call.id, f"✅ تم تعيين كومبو برايفت لـ {uid} - {flag} {name}", show_alert=True)
    admin_private_combo(call)

@bot.callback_query_handler(func=lambda call: call.data == "del_private_combo")
def del_private_combo_step1(call):
    if not is_admin(call.from_user.id):
        return
    user_states[call.from_user.id] = "del_private_user_id"
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔙 Back", callback_data="admin_private_combo", style='danger'))
    bot.edit_message_text("أدخل معرف المستخدم:", call.message.chat.id, call.message.message_id, reply_markup=markup)

@bot.message_handler(func=lambda msg: user_states.get(msg.from_user.id) == "del_private_user_id")
def del_private_combo_step2(message):
    try:
        uid = int(message.text)
        save_user(uid, private_combo_country=None)
        bot.reply_to(message, f"✅ تم مسح الكومبو البرايفت للمستخدم {uid}")
    except:
        bot.reply_to(message, "❌ معرف غير صحيح!")
    del user_states[message.from_user.id]

# ======================
# 🆕 دالة جديدة: جلب الأرقام المتاحة (غير المستخدمة) مع دعم private
# ======================
def get_available_numbers(country_code, combo_index=1, user_id=None):
    all_numbers = get_combo(country_code, combo_index, user_id)
    if not all_numbers:
        return []
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT assigned_number FROM users WHERE assigned_number IS NOT NULL AND assigned_number != ''")
    used_numbers = set(row[0] for row in c.fetchall())
    conn.close()
    available = [num for num in all_numbers if num not in used_numbers]
    return available

# ======================
# 🔄 الدوال الأساسية للتنظيف والمعالجة (كما في الأصل)
# ======================
def clean_html(text):
    if not text:
        return ""
    text = str(text)
    text = re.sub(r'<[^>]+>', '', text)
    text = text.strip()
    return text

def clean_number(number):
    if not number:
        return ""
    number = re.sub(r'\D', '', str(number))
    return number

def get_country_info(number):
    _, name, flag, short = get_country_details_smart(number)
    return name, flag, short

def mask_number(number):
    number = number.strip()
    if len(number) > 8:
        return number[:4] + "⁦⁦••••" + number[-3:]
    return number

def extract_otp(message):
    patterns = [
        r'(?:code|رمز|كود|verification|تحقق|otp|pin)[:\s]+[‎]?(\d{3,8}(?:[- ]\d{3,4})?)',
        r'(\d{3})[- ](\d{3,4})',
        r'\b(\d{4,8})\b',
        r'[‎](\d{3,8})',
    ]
    for pattern in patterns:
        match = re.search(pattern, message, re.IGNORECASE)
        if match:
            if len(match.groups()) > 1:
                return ''.join(match.groups())
            return match.group(1).replace(' ', '').replace('-', '')
    all_numbers = re.findall(r'\d{4,8}', message)
    if all_numbers:
        return all_numbers[0]
    return "N/A"

def detect_service(message):
    message_lower = message.lower()

    # القاموس الأساسي (زي ما هو)
    services = {
        "#WP": ["whatsapp", "واتساب", "واتس"],
        "#FB": ["facebook", "فيسبوك", "fb"],
        "#IG": ["instagram", "انستقرام", "انستا"],
        "#TG": ["telegram", "تيليجرام", "تلي"],
        "#TW": ["twitter", "تويتر", "x"],
        "#GG": ["google", "gmail", "جوجل", "جميل"],
        "#DC": ["discord", "ديسكورد"],
        "#LN": ["line", "لاين"],
        "#VB": ["viber", "فايبر"],
        "#SK": ["skype", "سكايب"],
        "#SC": ["snapchat", "سناب"],
        "#TT": ["tiktok", "تيك توك", "تيك"],
        "#AMZ": ["amazon", "امازون"],
        "#APL": ["apple", "ابل", "icloud"],
        "#MS": ["microsoft", "مايكروسوفت"],
        "#IN": ["linkedin", "لينكد"],
        "#UB": ["uber", "اوبر"],
        "#AB": ["airbnb", "ايربنب"],
        "#NF": ["netflix", "نتفلكس"],
        "#SP": ["spotify", "سبوتيفاي"],
        "#YT": ["youtube", "يوتيوب"],
        "#GH": ["github", "جيت هاب"],
        "#PT": ["pinterest", "بنتريست"],
        "#PP": ["paypal", "باي بال"],
        "#BK": ["booking", "بوكينج"],
        "#TL": ["tala", "تالا"],
        "#OLX": ["olx", "اوليكس"],
        "#STC": ["stcpay", "stc"],
    }

    # ✅ التحقق الأساسي (زي ما هو)
    for service_code, keywords in services.items():
        for keyword in keywords:
            if keyword in message_lower:
                return service_code

    # ✅ Fallback ذكي من صيغة رسالة OTP نفسها
    if "code" in message_lower or "verification" in message_lower:
        if "telegram" in message_lower:
            return "#TG"
        if "whatsapp" in message_lower:
            return "#WP"
        if "facebook" in message_lower:
            return "#FB"
        if "instagram" in message_lower:
            return "#IG"
        if "google" in message_lower or "gmail" in message_lower:
            return "#GG"
        if "twitter" in message_lower or "x.com" in message_lower:
            return "#TW"

    #  آخر حل
    return "Unknown"

def html_escape(text):
    return (str(text)
            .replace("&", "&amp;")
            .replace("<", "&lt;")   # مهم جداً
            .replace(">", "&gt;")
            .replace('"', "&quot;"))

def format_message(date_str, number, sms):
    country_name, country_flag, country_code = get_country_info(number)
    masked_num = mask_number(number)
    otp_code = extract_otp(sms)
    service = detect_service(sms)

    header = "• ✘ 𝙍𝘼𝙑𝙀𝙉 | 🏴☠️ • 𝙉𝙐𝙈𝘽𝙀𝙍 𝘽𝙊𝙏 𝙓  •"
    info_line = f"→ {country_flag} #{country_code} [{service}] {masked_num} ┥"
    sms_content = f"<blockquote>{html_escape(sms)}</blockquote>"
    time_content = f"<blockquote>⏰ ~ {date_str}</blockquote>"

    final_message = f"{header}\n{info_line}\n{sms_content}\n{time_content}"
    return final_message

# ======================
# 📡 دوال الاتصال بلوحة iVasms
# ======================

# --- دالة تسجيل الدخول إلى iVasms ---
def login_to_ivasms():
    """تسجيل الدخول باستخدام الكوكيز المحفوظة"""
    global _cookies_alert_sent, _login_in_progress, _cookies_expired
    if _login_in_progress:
        return IVASMS_DASHBOARD.get('is_logged_in', False)
    if _cookies_expired:
        return False  # مش هيحاول تاني لحد ما الكوكيز تتغير
    _login_in_progress = True
    try:
        dash    = IVASMS_DASHBOARD
        session = dash["session"]

        print(f"[{dash['name']}] محاولة تسجيل الدخول...")

        # تحميل الكوكيز من الملف أو الافتراضية
        saved = load_cookies_from_file()

        session.headers.update(get_active_headers())
        session.cookies.clear()

        # الكوكيز المحفوظة للمستخدم
        cookies_to_use = saved if saved else default_cookies
        if isinstance(cookies_to_use, list):
            for c in cookies_to_use:
                domain = c.get('domain', 'www.ivasms.com').lstrip('.')
                path = c.get('path', '/')
                session.cookies.set(c['name'], c['value'], domain=domain, path=path)
                session.cookies.set(c['name'], c['value'], domain='www.ivasms.com', path=path)
                session.cookies.set(c['name'], c['value'], domain='.ivasms.com', path=path)
        else:
            for name, value in cookies_to_use.items():
                session.cookies.set(name, value, domain='www.ivasms.com', path='/')
                session.cookies.set(name, value, domain='.ivasms.com', path='/')

        dashboard_resp = session.get(
            "https://www.ivasms.com/portal/sms/received",
            timeout=30, allow_redirects=True
        )

        print(f"[{dash['name']}] 🔍 URL بعد الدخول: {dashboard_resp.url}")
        print(f"[{dash['name']}] 🔍 Status: {dashboard_resp.status_code}")
        print(f"[{dash['name']}] 🔍 Cookies في الـ session: {list(session.cookies.keys())}")
        print(f"[{dash['name']}] 🔍 Cookies details:")
        for c in session.cookies:
            print(f"    {c.name} | domain={c.domain} | value={c.value[:30]}")
        print(f"[{dash['name']}] 🔍 Response (500 حرف):\n{dashboard_resp.text[200:700]}")

        is_expired = False
        expire_reason = ""

        if dashboard_resp.status_code != 200:
            is_expired = True
            expire_reason = f"رمز الاستجابة {dashboard_resp.status_code}"
        elif "login" in dashboard_resp.url.lower():
            is_expired = True
            expire_reason = "تم التحويل لصفحة تسجيل الدخول"

        if not is_expired:
            soup = BeautifulSoup(dashboard_resp.text, 'html.parser')
            csrf_meta = soup.find('meta', {'name': 'csrf-token'})
            csrf_token = csrf_meta.get('content') if csrf_meta else None
            if not csrf_token:
                token_input = soup.find('input', {'name': '_token'})
                csrf_token = token_input['value'] if token_input else None
            if not csrf_token:
                is_expired = True
                expire_reason = "لم يتم العثور على CSRF token"
            else:
                dash['csrf_token'] = csrf_token

        if is_expired:
            print(f"[{dash['name']}] ❌ الكوكيز انتهت ({expire_reason}) — البوت هيوقف المحاولات لحد ما تبعت كوكيز جديدة")
            dash['is_logged_in'] = False
            _cookies_expired = True
            mar = types.InlineKeyboardMarkup(row_width=1)
            mar.add(
                types.InlineKeyboardButton("📤 إرسال كوكيز جديدة", callback_data="cookies_send", style="success"),
                types.InlineKeyboardButton("🍪 لوحة إدارة الكوكيز", callback_data="admin_cookies_panel", style="primary"),
                types.InlineKeyboardButton("💻 شرح جلب الكوكيز من PC",    callback_data="cookies_guide_pc", style="primary"),
                types.InlineKeyboardButton("📱 شرح جلب الكوكيز من الفون", callback_data="cookies_guide_phone", style="primary")
            )
            # إرسال الإشعار مرة واحدة فقط بدون أي تكرار
            if not _cookies_alert_sent:
                _cookies_alert_sent = True
                for admin_id in ADMIN_IDS:
                    try:
                        bot.send_message(
                            admin_id,
                            "⚠️ <b>تنبيه: كوكيز iVasms انتهت!</b>\n\n"
                            "البوت متوقف حالياً عن استقبال الرسائل الجديدة.\n"
                            "يرجى تجديد الكوكيز من لوحة الإدارة للاستمرار 👇",
                            reply_markup=mar,
                            parse_mode="HTML"
                        )
                    except Exception:
                        pass
            return False

        print(f"[{dash['name']}] ✅ تسجيل الدخول ناجح بالكوكيز")
        dash['is_logged_in'] = True
        dash['cookies']      = session.cookies.get_dict()
        _cookies_expired     = False
        _cookies_alert_sent  = False
        return True

    except Exception as e:
        print(f"[{dash['name']}] ❌ خطأ في تسجيل الدخول: {e}")
        return False
    finally:
        _login_in_progress = False

# --- دالة جلب الرسائل من iVasms ---
def fetch_ivasms_messages():
    """جلب رسائل SMS من لوحة iVasms"""
    dash = IVASMS_DASHBOARD
    
    # التأكد من تسجيل الدخول
    if not dash.get('is_logged_in', False):
        if not login_to_ivasms():
            return []
    
    try:
        session  = dash['session']
        base_url = "https://www.ivasms.com"

        # استخدام CSRF token المحفوظ وتجديده فقط عند الحاجة لتجنب إرسال طلبات زائدة
        csrf_token = dash.get('csrf_token')
        if not csrf_token:
            dashboard_page = session.get(f"{base_url}/portal/sms/received", timeout=30)
            if dashboard_page.status_code != 200:
                print(f"[{dash['name']}] ❌ خطأ في استجابة صفحة الرسائل: {dashboard_page.status_code}")
                dash['is_logged_in'] = False
                return []
            soup_dash  = BeautifulSoup(dashboard_page.text, 'html.parser')
            csrf_meta  = soup_dash.find('meta', {'name': 'csrf-token'})
            csrf_token = csrf_meta.get('content') if csrf_meta else None
            if not csrf_token:
                token_input = soup_dash.find('input', {'name': '_token'})
                csrf_token  = token_input['value'] if token_input else None
            if not csrf_token:
                print(f"[{dash['name']}] ❌ مش قادر أجيب CSRF token")
                dash['is_logged_in'] = False
                return []
            dash['csrf_token'] = csrf_token

        headers = {
            'Referer':          f"{base_url}/portal/sms/received",
            'Origin':           base_url,
            'X-Requested-With': 'XMLHttpRequest',
            'Accept':           'application/json, text/javascript, */*; q=0.01',
            'sec-ch-ua':        '"Chromium";v="152", "Google Chrome";v="152", "Not-A.Brand";v="99"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Linux"',
            'sec-fetch-dest':   'empty',
            'sec-fetch-mode':   'cors',
            'sec-fetch-site':   'same-origin',
        }

        # جلب ملخص الرسائل لآخر 3 أيام
        today      = datetime.utcnow()
        start_date = (today - timedelta(days=3)).strftime('%m/%d/%Y')
        end_date   = today.strftime('%m/%d/%Y')

        sms_api_url     = f"{base_url}/portal/sms/received/getsms"
        summary_payload = {
            'from':   start_date,
            'to':     end_date,
            '_token': csrf_token
        }

        summary_resp = session.post(sms_api_url, headers=headers, data=summary_payload, timeout=30)
        if summary_resp.status_code == 419:
            print(f"[{dash['name']}] ⚠️ CSRF token منتهي، سيتم تحديثه في الدورة القادمة")
            dash['csrf_token'] = None
            return []
        if summary_resp.status_code == 403:
            print(f"[{dash['name']}] ❌ اعتراض Cloudflare (403)")
            dash['is_logged_in'] = False
            return []
        summary_resp.raise_for_status()
        
        # تحليل الـ HTML
        summary_soup  = BeautifulSoup(summary_resp.text, 'html.parser')
        country_groups = summary_soup.find_all('div', class_='rng')
        if not country_groups:
            country_groups = [el for el in summary_soup.find_all('div') if 'toggleRange' in el.get('onclick', '')]

        if not country_groups:
            # عدم وجود مجموعات يعني ببساطة عدم وصول رسائل SMS جديدة في هذا النطاق الزمني
            return []

        group_ids = []
        for group in country_groups:
            onclick = group.get('onclick', '')
            match = re.search(r"toggleRange\('([^']+)'\s*,\s*'([^']+)'\)", onclick)
            if match:
                range_id = match.group(1).strip()
                safe_id  = match.group(2).strip()
                if range_id not in [g[0] for g in group_ids]:
                    group_ids.append((range_id, safe_id))

        print(f"[{dash['name']}] 📋 مجموعات: {[g[0] for g in group_ids]}")
        if not group_ids:
            return []

        all_messages    = []
        numbers_url     = f"{base_url}/portal/sms/received/getsms/number"
        sms_details_url = f"{base_url}/portal/sms/received/getsms/number/sms"

        for (range_id, safe_id) in group_ids:
            numbers_payload = {
                'start':  start_date,
                'end':    end_date,
                'range':  range_id,
                '_token': csrf_token
            }
            numbers_resp = session.post(numbers_url, headers=headers, data=numbers_payload, timeout=30)
            numbers_soup = BeautifulSoup(numbers_resp.text, 'html.parser')

            phone_numbers = []
            for el in numbers_soup.find_all(['div', 'span', 'li', 'a', 'td']):
                onclick_val = el.get('onclick', '')
                if onclick_val:
                    nm = re.search(r"'(\d{7,})'", onclick_val)
                    if nm and nm.group(1) not in phone_numbers:
                        phone_numbers.append(nm.group(1))
                else:
                    txt = el.get_text(strip=True)
                    if re.fullmatch(r'\d{7,15}', txt) and txt not in phone_numbers:
                        phone_numbers.append(txt)

            if not phone_numbers:
                continue

            for phone in phone_numbers:
                sms_payload = {
                    'start':  start_date,
                    'end':    end_date,
                    'Number': phone,
                    'Range':  range_id,
                    '_token': csrf_token
                }
                sms_resp = session.post(sms_details_url, headers=headers, data=sms_payload, timeout=30)
                sms_soup = BeautifulSoup(sms_resp.text, 'html.parser')

                rows = sms_soup.select('table tbody tr')
                for row in rows:
                    msg_div = row.find('div', class_='msg-text')
                    if not msg_div:
                        continue
                    sms_text = msg_div.get_text(separator=' ').strip()
                    if not sms_text:
                        continue
                    sender_tag = row.find('span', class_='cli-tag')
                    sender     = sender_tag.get_text(strip=True) if sender_tag else 'Unknown'
                    message_id = f"{phone}-{sms_text[:50]}"
                    all_messages.append({
                        'id':        message_id,
                        'number':    phone,
                        'text':      sms_text,
                        'sender':    sender,
                        'country':   range_id,
                        'timestamp': datetime.utcnow().isoformat()
                    })
        
        print(f"[{dash['name']}] ✅ تم جلب {len(all_messages)} رسالة")
        return all_messages
        
    except Exception as e:
        print(f"[{dash['name']}] ❌ خطأ في جلب الرسائل: {e}")
        traceback.print_exc()
        # في حالة فشل الجلب، قد تكون الجلسة منتهية
        dash['is_logged_in'] = False
        return []

# ======================
# 🔄 الدالة المعدلة لإرسال OTP للمستخدم + الجروب
# ======================
def send_otp_to_user_and_group(date_str, number, sms):
    # استخراج الكود
    otp_code = extract_otp(sms)
    
    # معرفة الدولة والعلم تلقائيًا
    country_name, country_flag, country_code = get_country_info(number)
    
    # معرفة الخدمة
    service = detect_service(sms)
    
    # الحصول على user_id إذا موجود
    user_id = get_user_by_number(number)
    log_otp(number, otp_code, sms, user_id)
    
    if user_id:
        try:
            lang = get_user_language(user_id)
            markup = types.InlineKeyboardMarkup()
            markup.row(
                types.InlineKeyboardButton("• Channel •", url="https://t.me/Raven_xx24", style="primary"),
                types.InlineKeyboardButton("• Developer •", url="https://t.me/P_X_24", style="primary")
            )
            user_msg = get_text(
                "private_otp_msg",
                lang,
                country_name=safe_html(country_name),
                country_flag=country_flag,
                service=safe_html(service),
                number=safe_html(number),
                date_str=safe_html(date_str),
                otp_code=safe_html(otp_code)
            )
            bot.send_message(
                user_id,
                user_msg,
                reply_markup=markup,
                parse_mode="HTML"
            )
        except Exception as e:
            print(f"[!] فشل إرسال OTP للمستخدم {user_id}: {e}")
    # إرسال نفس الرسالة للجروب
    text = format_message(date_str, number, sms)
    send_to_telegram_group(text, otp_code)

def delete_message_after_delay(chat_id, message_id, delay=300):
    """تحذف الرسالة بعد مرور delay ثانية"""
    time.sleep(delay)
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/deleteMessage"
        payload = {"chat_id": chat_id, "message_id": message_id}
        requests.post(url, data=payload)
    except Exception as e:
        print(f"❌ فشل حذف الرسالة: {e}")

def send_to_telegram_group(text, otp_code):
    success_count = 0

    markup = types.InlineKeyboardMarkup()

    try:
        copy_btn = types.InlineKeyboardButton(
            f"📋🔑 {otp_code}",
            copy_text=types.CopyTextButton(text=str(otp_code)),
            style='success'
        )
    except AttributeError:
        copy_btn = types.InlineKeyboardButton(
            f"📋🔑 {otp_code}",
            callback_data=f"copy_{otp_code}",
            style='success'
        )
    markup.add(copy_btn)

    markup.row(
        types.InlineKeyboardButton("• Channel •", url="https://t.me/Raven_xx24", style='primary'),
        types.InlineKeyboardButton("• Developer •", url="https://t.me/P_X_24", style='primary')
    )

    for chat_id in CHAT_IDS:
        try:
            bot.send_message(
                chat_id,
                text,
                parse_mode="HTML",
                reply_markup=markup,
                disable_web_page_preview=True
            )
            print(f"[+] تم إرسال الرسالة بنجاح إلى: {chat_id}")
            success_count += 1
        except Exception as e:
            print(f"[!] خطأ في الإرسال لـ {chat_id}: {e}")

    return success_count > 0
@bot.callback_query_handler(func=lambda call: call.data.startswith("copy_"))
def handle_copy_button(call):
    otp_code = call.data.split("_", 1)[1]
    bot.answer_callback_query(call.id, f"✅ تم نسخ الكود: {otp_code}", show_alert=True)

@bot.callback_query_handler(func=lambda call: call.data.startswith("copy_num_"))
def handle_copy_num_button(call):
    num = call.data.split("copy_num_", 1)[1]
    bot.answer_callback_query(call.id, f"✅ تم نسخ الرقم: +{num}", show_alert=True)

@bot.callback_query_handler(func=lambda call: call.data.startswith("copy_range_"))
def handle_copy_range_button(call):
    r_code = call.data.split("copy_range_", 1)[1]
    bot.answer_callback_query(call.id, f"✅ كود النطاق:\n{r_code}", show_alert=True)

def is_live_stream_enabled():
    val = get_setting('live_stream_enabled')
    if val is None:
        set_setting('live_stream_enabled', '1')
        return True
    return str(val) == '1'

def set_live_stream_enabled(enabled: bool):
    set_setting('live_stream_enabled', '1' if enabled else '0')

def get_live_stream_chat_id():
    val = get_setting('live_stream_chat_id')
    if val:
        val_str = str(val).strip()
        if val_str:
            return val_str
    return None

def set_live_stream_chat_id(chat_id):
    if chat_id:
        set_setting('live_stream_chat_id', str(chat_id).strip())
    else:
        set_setting('live_stream_chat_id', '')

# ======================
# 📡 مراقب وبث الرسائل الحية للجروب (Live Traffic Streamer)
# ======================
SENT_LIVE_FILE = os.path.join(BASE_DIR, "sent_live_messages.json")

def format_live_stream_message(m):
    """
    تنسيق رسالة البث المباشر الخاصة بجروب التيليجرام بكافة التفاصيل
    بحيث تكون منفصلة ومميزة تماماً عن رسالة أكواد المستخدمين العادية
    """
    flag = m.get('flag') or '🌐'
    c_name = m.get('country_name') or 'Unknown'
    c_code = m.get('country_code') or ''
    range_name = (m.get('range') or '').strip()
    app_name = m.get('app') or 'SMS'
    number = m.get('number') or ''
    sms_text = html_escape(m.get('text') or '')
    time_str = m.get('time') or ''
    otp_code = extract_otp(m.get('text') or '')

    c_code_line = f" (+{c_code})" if c_code else ""
    otp_line = f"\n🔐 <b>كود التحقق (OTP):</b> <code>{otp_code}</code>" if otp_code else ""

    return (
        "🌐 <b>LIVE TRAFFIC • بث مباشر</b>\n\n"
        f"🌍 <b>الدولة:</b> {flag} <b>{c_name}</b><code>{c_code_line}</code>\n"
        f"🏷️ <b>كود النطاق:</b> <code>{range_name}</code>\n"
        f"⚙️ <b>الخدمة / التطبيق:</b> <b>[{app_name}]</b>\n"
        f"☎️ <b>الرقم التجريبي:</b> <code>+{number}</code>{otp_line}\n\n"
        f"📩 <b>الرسالة المستلمة:</b>\n<blockquote>{sms_text}</blockquote>\n"
        f"⏰ <b>التوقيت:</b> <code>{time_str}</code>"
    )

def live_stream_worker():
    """
    مراقب البث المباشر: يسحب تلقائياً الرسائل والأكواد الحية من iVasms
    ويرسلها حصرياً لمجموعة البث المباشر المحددة من لوحة الأدمن
    """
    print("[LiveStream] 🚀 بدء تشغيل مراقب البث المباشر لجروب التيليجرام...")
    sent_live_ids = set()
    if os.path.exists(SENT_LIVE_FILE):
        try:
            with open(SENT_LIVE_FILE, 'r', encoding='utf-8') as f:
                saved = json.load(f)
                if isinstance(saved, list):
                    sent_live_ids = set(saved)
        except Exception:
            pass

    first_run = True

    while True:
        try:
            time.sleep(4)
            if not is_live_stream_enabled():
                continue

            target_chat = get_live_stream_chat_id()
            if not target_chat:
                # إذا لم يتم تعيين مجموعة خاصة بالبث المباشر حتى الآن، لا نرسل لمجموعة المستخدمين
                continue

            if _cookies_expired:
                continue

            import ivasms_manager as _im
            messages = _im.fetch_live_stream_messages(limit=10)
            if not messages:
                continue

            if first_run:
                for m in messages:
                    sent_live_ids.add(str(m['id']))
                first_run = False
                continue

            unseen = [m for m in messages if str(m['id']) not in sent_live_ids]
            if not unseen:
                continue

            # نحفظ كل الرسائل كـ seen حتى لا تتراكم
            for m in unseen:
                sent_live_ids.add(str(m['id']))

            # نرسل فقط أحدث رسالتين كحد أقصى لكل دورة لتجنب سبام التيليجرام وحظر 429
            to_send = unseen[-2:]
            new_sent = 0

            for m in to_send:
                number = m.get('number', '')
                range_name = (m.get('range') or '').strip()
                if not range_name:
                    range_name = f"{m.get('country_name', 'RANGE').upper()} {m.get('country_code', '')}"

                group_text = format_live_stream_message(m)

                # زر واحد فقط يحتوي على كود النطاق لنسخه بنقرة واحدة ملون بنفس ستايل رسالة الكود
                markup = types.InlineKeyboardMarkup()
                try:
                    markup.add(types.InlineKeyboardButton(
                        f"📋 {range_name}",
                        copy_text=types.CopyTextButton(text=range_name),
                        style='success'
                    ))
                except Exception:
                    markup.add(types.InlineKeyboardButton(
                        f"📋 {range_name}",
                        callback_data=f"copy_range_{range_name[:30]}",
                        style='success'
                    ))

                try:
                    bot.send_message(
                        target_chat,
                        group_text,
                        parse_mode="HTML",
                        reply_markup=markup,
                        disable_web_page_preview=True
                    )
                    new_sent += 1
                except Exception as e:
                    err_s = str(e)
                    if "429" in err_s or "Too Many Requests" in err_s:
                        m_wait = re.search(r'retry after (\d+)', err_s)
                        wait_sec = int(m_wait.group(1)) + 1 if m_wait else 15
                        print(f"[LiveStream] ⏳ انتظار مهلة Telegram Rate Limit ({wait_sec}s)...")
                        time.sleep(wait_sec)
                    else:
                        print(f"[LiveStream] خطأ إرسال لـ {target_chat}: {e}")

                user_id = get_user_by_number(number)
                if user_id:
                    try:
                        lang = get_user_language(user_id)
                        user_markup = types.InlineKeyboardMarkup()
                        user_markup.row(
                            types.InlineKeyboardButton("• Channel •", url="https://t.me/Raven_xx24", style="primary"),
                            types.InlineKeyboardButton("• Developer •", url="https://t.me/P_X_24", style="primary")
                        )
                        user_msg = get_text(
                            "private_otp_msg",
                            lang,
                            country_name=safe_html(m.get('country_name', '')),
                            country_flag=m.get('flag', ''),
                            service=safe_html(m.get('app', '')),
                            number=safe_html(number),
                            date_str=safe_html(m.get('time', '')),
                            otp_code=safe_html(extract_otp(m.get('text', '')) or "N/A")
                        )
                        bot.send_message(
                            user_id,
                            user_msg,
                            reply_markup=user_markup,
                            parse_mode="HTML"
                        )
                    except Exception as e:
                        print(f"[LiveStream] فشل إرسال خاص للمستخدم {user_id}: {e}")

                time.sleep(3.5)  # مهلة أمان بين الرسائل لمنع تجاوز حد تليجرام

            if new_sent > 0:
                print(f"[LiveStream] 📡 تم بث رسائل حية جديدة للمجموعة بنجاح ✅")
                try:
                    with open(SENT_LIVE_FILE, 'w', encoding='utf-8') as f:
                        json.dump(list(sent_live_ids)[-1000:], f)
                except Exception:
                    pass

            if len(sent_live_ids) > 3000:
                sent_live_ids = set(list(sent_live_ids)[-1500:])

        except Exception as ex:
            print(f"[LiveStream] ❌ خطأ في تشغيل البث: {ex}")
            time.sleep(5)

# ======================
# ⏰ مؤقت التذكير الدوري للمجموعات (كل ساعة)
# ======================
def hourly_group_reminder_worker():
    """
    إرسال رسالة تذكيرية دورية كل ساعة للمجموعات التي يكون فيها البوت مشرفاً (Admin)
    تحتوي على زر أحمر للدخول للبوت
    """
    print("[Reminder] 🚀 بدء تشغيل مؤقت التذكير الدوري للمجموعات (مرة كل ساعة)...")
    time.sleep(25)  # مهلة تمهيدية عند بداية التشغيل

    while True:
        try:
            bot_me = bot.get_me()
            bot_username = bot_me.username or "Free_Numberv1bot"
            bot_id = bot_me.id

            groups = get_all_bot_groups()

            reminder_text = (
                "🌐 <b>PLATFORM: iVASMS</b>\n\n"
                "⚡ <b>منصة iVASMS للأرقام وتفعيل الحسابات</b>\n"
                "📩 استلام فوري لرسائل SMS وأكواد التحقق لكافة التطبيقات!\n"
                "🚀 اضغط على الزر بالأسفل لبدء الاستخدام في المحادثة الخاصة ⬇️"
            )

            markup = types.InlineKeyboardMarkup()
            try:
                markup.add(types.InlineKeyboardButton(
                    "⚡ الدخول إلى البوت | START BOT",
                    url=f"https://t.me/{bot_username}?start=group_reminder",
                    style='danger'
                ))
            except Exception:
                markup.add(types.InlineKeyboardButton(
                    "⚡ الدخول إلى البوت | START BOT",
                    url=f"https://t.me/{bot_username}?start=group_reminder"
                , style='danger'))

            sent_count = 0
            for chat_id, title in groups:
                try:
                    # تحقق هل البوت أدمن في المجموعة
                    member = bot.get_chat_member(chat_id, bot_id)
                    if member.status in ['administrator', 'creator']:
                        sent_m = bot.send_message(
                            chat_id,
                            reminder_text,
                            parse_mode="HTML",
                            reply_markup=markup,
                            disable_web_page_preview=True
                        )
                        # الحذف التلقائي بعد دقيقة واحدة (60 ثانية) لمنع تراكم الرسائل
                        threading.Thread(
                            target=delete_message_after_delay,
                            args=(chat_id, sent_m.message_id, 60),
                            daemon=True
                        ).start()
                        sent_count += 1
                        print(f"[Reminder] ✅ تم إرسال رسالة التذكير للمجموعة (حذف تلقائي بعد 60ث): {title} ({chat_id})")
                        time.sleep(2)
                    else:
                        print(f"[Reminder] ⚠️ البوت ليس مشرفاً في {title} ({chat_id}) — تم التخطي")
                except Exception as e:
                    print(f"[Reminder] ❌ تعذر الإرسال للمجموعة {chat_id}: {e}")

            if sent_count > 0:
                print(f"[Reminder] 📢 اكتملت دورة التذكير بنجاح — تم الإرسال لـ {sent_count} مجموعة")

        except Exception as e:
            print(f"[Reminder] خطأ في دورة التذكير: {e}")

        # انتظار ساعة كاملة (3600 ثانية)
        time.sleep(3600)

# ======================
# 🔄 الحلقة الرئيسية (معدلة للوحة iVasms فقط)
# ======================
def main_loop():
    global REFRESH_INTERVAL
    REFRESH_INTERVAL = 6  # 6 ثواني للفحص الآمن لتجنب حظر Cloudflare
    
    # قائمة باللوحة الوحيدة
    DASHBOARDS = [IVASMS_DASHBOARD]
    
    # ملف لتخزين معرفات الرسائل المرسلة
    SENT_MESSAGES_FILE = "mafia_sent_messages.json"
    sent_messages = {}
    try:
        if os.path.exists(SENT_MESSAGES_FILE):
            with open(SENT_MESSAGES_FILE, 'r') as f:
                data = json.load(f)
                sent_messages = {mid: "" for mid in data} if isinstance(data, list) else data
    except Exception as e:
        print(f"⚠️ خطأ في تحميل الرسائل المرسلة: {e}")

    print("=" * 60)
    print(f"🚀 بدء مراقبة لوحة iVasms (كل {REFRESH_INTERVAL} ثوانٍ)")
    print("=" * 60)

    consecutive_errors = {dash["name"]: 0 for dash in DASHBOARDS}

    # تسجيل الدخول الأولي + إشعار لو الكوكيز منتهية
    for dash in DASHBOARDS:
        if not dash.get('is_logged_in', False):
            success = login_to_ivasms()
            if not success:
                mar = types.InlineKeyboardMarkup(row_width=1)
                mar.add(
                    types.InlineKeyboardButton("💻 شرح جلب الكوكيز من PC",    callback_data="cookies_guide_pc", style="primary"),
                    types.InlineKeyboardButton("📱 شرح جلب الكوكيز من الفون", callback_data="cookies_guide_phone", style="primary"),
                    types.InlineKeyboardButton("📤 ابعت الكوكيز الجديدة",     callback_data="cookies_send", style="success")
                )
                def _send_first_alert():
                    for admin_id in ADMIN_IDS:
                        try:
                            bot.send_message(
                                admin_id,
                                "👋 <b>أهلاً! البوت اشتغل للمرة الأولى أو الكوكيز منتهية</b>\n\n"
                                "⚠️ محتاج تجيب الكوكيز الخاصة بحسابك على iVasms\n"
                                "عشان البوت يبدأ يشتغل معاك.\n\n"
                                "اختر طريقة جلب الكوكيز 👇",
                                reply_markup=mar,
                                parse_mode="HTML"
                            )
                        except Exception:
                            pass
                import threading as _th2
                _th2.Thread(target=_send_first_alert, daemon=True).start()

    while True:
        for dash in DASHBOARDS:
            if _cookies_expired:
                time.sleep(15)
                continue
            try:
                print(f"[{dash['name']}] ⏱️ جلب الرسائل...")
                
                # جلب الرسائل
                messages = fetch_ivasms_messages()
                
                if messages:
                    new_messages = 0
                    # معالجة الرسائل من الأحدث إلى الأقدم
                    for msg in messages:
                        msg_id = msg['id']
                        
                        if msg_id not in sent_messages:
                            # استخراج البيانات
                            number = clean_number(msg['number'])
                            sms_text = msg['text']
                            date_str = msg['timestamp']
                            
                            # إرسال الرسالة
                            send_otp_to_user_and_group(date_str, number, sms_text)
                            
                            # إضافة إلى قائمة المرسلة
                            sent_messages[msg_id] = datetime.utcnow().isoformat()
                            new_messages += 1
                    
                    if new_messages > 0:
                        print(f"[{dash['name']}] ✅ تم إرسال {new_messages} رسالة جديدة")
                        
                        # حفظ قائمة الرسائل المرسلة
                        try:
                            with open(SENT_MESSAGES_FILE, 'w') as f:
                                json.dump(list(sent_messages)[-1000:], f)  # حفظ آخر 1000 رسالة فقط
                        except Exception as e:
                            print(f"⚠️ خطأ في حفظ الرسائل المرسلة: {e}")
                    
                    consecutive_errors[dash["name"]] = 0
                else:
                    print(f"[{dash['name']}] [=] لا توجد رسائل جديدة")
                    # لو الجلسة منتهية والكوكيز مش منتهية، أعد تسجيل الدخول
                    if not dash.get('is_logged_in', False) and not _login_in_progress and not _cookies_expired:
                        print(f"[{dash['name']}] 🔄 إعادة محاولة تسجيل الدخول...")
                        threading.Thread(target=login_to_ivasms, daemon=True).start()

                # تنظيف الذاكرة
                if len(sent_messages) > 2000:
                    sent_messages = set(list(sent_messages)[-1000:])

            except Exception as e:
                consecutive_errors[dash["name"]] += 1
                print(f"[{dash['name']}] ❌ خطأ ({consecutive_errors[dash['name']]}): {e}")
                if consecutive_errors[dash["name"]] >= 5:
                    print(f"[{dash['name']}] ⛔ إعادة تسجيل الدخول بعد 5 أخطاء")
                    dash['is_logged_in'] = False
                    if not _login_in_progress:
                        threading.Thread(target=login_to_ivasms, daemon=True).start()
                    consecutive_errors[dash["name"]] = 0

            time.sleep(REFRESH_INTERVAL)


# ======================
# 🔄 نظام إدارة وفحص الكوكيز المتطور
# ======================
def build_cookies_panel_markup(lang='ar'):
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton(get_text("cookies_btn_check", lang), callback_data="cookies_check_now", style='primary'),
        types.InlineKeyboardButton(get_text("cookies_btn_send", lang), callback_data="cookies_send", style='success'),
        types.InlineKeyboardButton(get_text("cookies_btn_test_old", lang), callback_data="test_old_pull_start", style='primary'),
        types.InlineKeyboardButton(get_text("cookies_btn_pc", lang), callback_data="cookies_guide_pc", style='primary'),
        types.InlineKeyboardButton(get_text("cookies_btn_phone", lang), callback_data="cookies_guide_phone", style='primary'),
        types.InlineKeyboardButton(get_text("admin_btn_back", lang), callback_data="admin_panel", style='danger')
    )
    return markup

def get_cookies_status_text(lang='ar'):
    is_active = IVASMS_DASHBOARD.get('is_logged_in', False) and not _cookies_expired
    status_icon = "🟢" if is_active else "🔴"
    status_str = get_text("cookies_active", lang) if is_active else get_text("cookies_expired", lang)
    saved = load_cookies_from_file()
    cookies_count = len(saved) if isinstance(saved, (list, dict)) else 0
    last_up = _last_cookies_update or get_text("not_specified", lang)

    text = (
        f"🍪 <b>{get_text('cookies_panel_title', lang)}</b>\n\n"
        f"• <b>{get_text('admin_bot_status', lang)}:</b> {status_icon} <u>{status_str}</u>\n"
        f"• <b>{get_text('cookies_saved_count', lang)}:</b> <code>{cookies_count}</code>\n"
        f"• <b>{get_text('cookies_last_up', lang)}:</b> <code>{last_up}</code>\n"
        f"• <b>{get_text('cookies_storage_file', lang)}:</b> <code>mafia_ck_4235.json</code>\n\n"
        "⚡ <b>Features:</b>\n"
        "• Support TXT files from browser extension directly.\n"
        "• Automated live verification before applying cookies.\n"
        "• Zero-loss safety: existing cookies kept safe if check fails."
    )
    return text

@bot.message_handler(commands=['cookies'])
def cmd_cookies(message):
    lang = get_user_language(message.from_user.id)
    if not is_admin(message.from_user.id):
        return
    bot.reply_to(
        message,
        get_cookies_status_text(lang),
        reply_markup=build_cookies_panel_markup(lang),
        parse_mode="HTML"
    )

@bot.callback_query_handler(func=lambda call: call.data in [
    "admin_cookies_panel", "cookies_main", "cookies_check_now",
    "cookies_send", "cookies_guide_pc", "cookies_guide_phone",
    "test_old_pull_start"
])
def cookies_callback(call):
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "⚠️ هذا القسم للمطورين فقط.", show_alert=True)
        return

    chat_id = call.message.chat.id
    msg_id  = call.message.message_id

    lang = get_user_language(call.from_user.id)
    if call.data in ["admin_cookies_panel", "cookies_main"]:
        try:
            bot.edit_message_text(
                get_cookies_status_text(lang),
                chat_id, msg_id,
                reply_markup=build_cookies_panel_markup(lang),
                parse_mode="HTML"
            )
        except Exception:
            bot.send_message(
                chat_id,
                get_cookies_status_text(lang),
                reply_markup=build_cookies_panel_markup(lang),
                parse_mode="HTML"
            )
        bot.answer_callback_query(call.id)

    elif call.data == "cookies_check_now":
        bot.answer_callback_query(call.id, "⏳ جاري فحص الكوكيز الحالية...")
        try:
            bot.edit_message_text(
                "⏳ <b>جاري فحص الكوكيز الحالية مع موقع iVasms...</b>\n\nيرجى الانتظار بضع ثوانٍ.",
                chat_id, msg_id,
                parse_mode="HTML"
            )
        except Exception:
            pass

        def _do_check():
            saved = load_cookies_from_file()
            if not saved:
                mar = types.InlineKeyboardMarkup(row_width=1)
                mar.add(
                    types.InlineKeyboardButton("📤 رفع ملف TXT أو كود JSON", callback_data="cookies_send", style="success"),
                    types.InlineKeyboardButton("🔙 رجوع", callback_data="admin_cookies_panel", style="danger")
                )
                try:
                    bot.edit_message_text(
                        "⚠️ <b>لا توجد كوكيز محفوظة حالياً!</b>\n\nيرجى رفع ملف الكوكيز أولاً.",
                        chat_id, msg_id,
                        reply_markup=mar,
                        parse_mode="HTML"
                    )
                except Exception:
                    pass
                return

            res = verify_and_test_cookies(saved)
            if len(res) == 4:
                ok, msg, token, matched_hdrs = res
            else:
                ok, msg, token = res[:3]
                matched_hdrs = None

            mar = types.InlineKeyboardMarkup(row_width=1)
            mar.add(
                types.InlineKeyboardButton("📤 رفع كوكيز جديدة", callback_data="cookies_send", style="success"),
                types.InlineKeyboardButton("🔄 إعادة الفحص", callback_data="cookies_check_now", style="primary"),
                types.InlineKeyboardButton("🔙 لوحة الكوكيز", callback_data="admin_cookies_panel", style="danger")
            )

            global _cookies_expired, _cookies_alert_sent
            if ok:
                IVASMS_DASHBOARD['is_logged_in'] = True
                if token:
                    IVASMS_DASHBOARD['csrf_token'] = token
                if matched_hdrs:
                    apply_cookies(saved, csrf_token=token, custom_headers=matched_hdrs)
                _cookies_expired = False
                _cookies_alert_sent = False
                res_text = (
                    "🟢 <b>نتيجة الفحص: الكوكيز تعمل بنجاح 100%!</b>\n\n"
                    "• <b>الموقع:</b> <code>ivasms.com</code> ✅\n"
                    "• <b>صفحة الرسائل:</b> <code>200 OK</code> ✅\n"
                    "• <b>رمز الحماية CSRF:</b> متوفر وصحيح ✅\n"
                    "• <b>الحالة:</b> البوت متصل وجاهز لسحب رسائل الـ OTP فوراً 🚀"
                )
            else:
                IVASMS_DASHBOARD['is_logged_in'] = False
                _cookies_expired = True
                res_text = (
                    "🔴 <b>نتيجة الفحص: الكوكيز غير صالحة أو منتهية!</b>\n\n"
                    f"• <b>السبب:</b> {msg}\n\n"
                    "⚠️ <b>الحل:</b> قم بتسجيل الدخول في المتصفح وتصدير كوكيز جديدة، ثم اضغط زر 'رفع كوكيز جديدة'."
                )

            try:
                bot.edit_message_text(res_text, chat_id, msg_id, reply_markup=mar, parse_mode="HTML")
            except Exception:
                bot.send_message(chat_id, res_text, reply_markup=mar, parse_mode="HTML")

        threading.Thread(target=_do_check, daemon=True).start()

    elif call.data == "cookies_send":
        cancel_mar = types.InlineKeyboardMarkup([[
            types.InlineKeyboardButton("🔙 إلغاء والرجوع", callback_data="admin_cookies_panel", style="danger")
        ]])
        prompt_text = (
            "📤 <b>إرسال الكوكيز الجديدة</b>\n\n"
            "يمكنك إرسال الكوكيز بإحدى طريقتين:\n\n"
            "1️⃣ <b>رفع ملف نصي:</b> أرسل ملف <code>.txt</code> (مثل الملف المستخرج من إضافة Get cookies.txt).\n"
            "2️⃣ <b>إرسال نص مباشر:</b> الصق كود JSON أو أسطر Netscape هنا في الشات.\n\n"
            "🛡️ <b>الفحص التلقائي:</b>\n"
            "سيتم اختبار الكوكيز فوراً مع موقع iVasms للتأكد من صلاحيتها. لن يتم تثبيت الكوكيز إلا إذا نجح الاتصال بنسبة 100%.\n\n"
            "🔙 للإلغاء أرسل: <code>الغاء</code>"
        )
        try:
            bot.edit_message_text(prompt_text, chat_id, msg_id, reply_markup=cancel_mar, parse_mode="HTML")
        except Exception:
            bot.send_message(chat_id, prompt_text, reply_markup=cancel_mar, parse_mode="HTML")
        bot.register_next_step_handler(call.message, receive_new_cookies_enhanced)
        bot.answer_callback_query(call.id)

    elif call.data == "cookies_guide_pc":
        mar = types.InlineKeyboardMarkup(row_width=1)
        mar.add(
            types.InlineKeyboardButton("📤 رفع ملف TXT أو كود JSON", callback_data="cookies_send", style="success"),
            types.InlineKeyboardButton("🔙 رجوع للوحة الكوكيز", callback_data="admin_cookies_panel", style="danger")
        )
        guide_pc = (
            "💻 <b>جلب الكوكيز من الكمبيوتر (PC أو لاب توب)</b>\n\n"
            "1️⃣ افتح متصفح Chrome أو Firefox أو Edge.\n"
            "2️⃣ افتح الموقع وسجل دخول:\n"
            "<code>https://www.ivasms.com/login</code>\n"
            "3️⃣ ادخل إلى صفحة الرسائل الواردة:\n"
            "<code>https://www.ivasms.com/portal/sms/received</code>\n"
            "4️⃣ قم بتثبيت إضافة <b>Get cookies.txt LOCALLY</b> أو <b>Cookie-Editor</b> من متجر المتصفح.\n"
            "5️⃣ افتح الإضافة واضغط:\n"
            "• إذا كانت <b>Get cookies.txt</b>: اضغط <b>Export</b> وسينزل ملف <code>.txt</code>.\n"
            "• إذا كانت <b>Cookie-Editor</b>: اضغط <b>Export as JSON</b> وانسخ النص.\n"
            "6️⃣ ارجع للبوت وارفع الملف <code>.txt</code> أو الصق النص هنا مباشرة 👇"
        )
        try:
            bot.edit_message_text(guide_pc, chat_id, msg_id, reply_markup=mar, parse_mode="HTML")
        except Exception:
            pass
        bot.answer_callback_query(call.id)

    elif call.data == "test_old_pull_start":
        cancel_mar = types.InlineKeyboardMarkup([[
            types.InlineKeyboardButton("🔙 إلغاء والرجوع", callback_data="admin_cookies_panel", style="danger")
        ]])
        prompt_text = (
            "📅 <b>اختبار سحب رسائل قديمة من الموقع</b>\n\n"
            "أدخل تاريخ البداية المطلوب لسحب الرسائل:\n"
            "• بالصيغة: <code>DD/MM/YYYY</code> (مثال: <code>01/01/2026</code> أو <code>1/1/2026</code>)\n"
            "• أو أرسل كلمة: <code>الافتراضي</code> لاستخدام تاريخ <code>01/01/2026</code>.\n\n"
            "⚡ <b>ماذا سيحدث؟</b>\n"
            "سيقوم البوت بالاتصال بالموقع وسحب حتى 10 رسائل قديمة من هذا التاريخ وإرسالها فوراً للمجموعة الرسمية بالتنسيق الجديد وأزرار النسخ لتأكيد عمل السحب بنجاح.\n\n"
            "🔙 للإلغاء أرسل: <code>الغاء</code>"
        )
        try:
            bot.edit_message_text(prompt_text, chat_id, msg_id, reply_markup=cancel_mar, parse_mode="HTML")
        except Exception:
            bot.send_message(chat_id, prompt_text, reply_markup=cancel_mar, parse_mode="HTML")
        bot.register_next_step_handler(call.message, handle_test_old_pull_date)
        bot.answer_callback_query(call.id)

    elif call.data == "cookies_guide_phone":
        mar = types.InlineKeyboardMarkup(row_width=1)
        mar.add(
            types.InlineKeyboardButton("📤 رفع ملف TXT أو كود JSON", callback_data="cookies_send", style="success"),
            types.InlineKeyboardButton("🔙 رجوع للوحة الكوكيز", callback_data="admin_cookies_panel", style="danger")
        )
        guide_phone = (
            "📱 <b>جلب الكوكيز من الهاتف وتخطي حظر Cloudflare (403):</b>\n\n"
            "🌐 <b>المتصفحات المدعومة على الهاتف:</b>\n"
            "• <b>متصفح Yandex Browser</b> (الأسهل والأفضل) 🟢\n"
            "• <b>متصفح Kiwi Browser</b> 🟢\n\n"
            "⚠️ <b>أهم شرطين لنجاح الكوكيز من الهاتف:</b>\n"
            "1️⃣ <b>وضع الكمبيوتر (Desktop site):</b> في متصفح Yandex أو Kiwi، اضغط على القائمة (⋮) وفعّل خيار «إصدار الكمبيوتر / الموقع المخصص للكمبيوتر» 💻 قبل فتح الموقع، حتى تتطابق بصمة المتصفح تماماً.\n"
            "2️⃣ <b>شبكة الإنترنت (Wi-Fi):</b> اتصل بنفس شبكة الواي فاي وتجنب باقة الهاتف (4G/5G) لأن كلاودفلير يربط الكوكي بعنوان الـ IP.\n\n"
            "<b>طريقة استخراج الكوكيز من Yandex Browser:</b>\n"
            "1️⃣ حمّل متصفح <b>Yandex Browser</b> من متجر Play Store.\n"
            "2️⃣ افتح المتصفح وادخل لسوق Chrome Web Store وثبّت إضافة <b>Cookie-Editor</b>.\n"
            "3️⃣ اضغط على الثلاث نقاط (⋮) في أسفل المتصفح وفعّل خيار <b>«إصدار الكمبيوتر» (Desktop site)</b> 💻.\n"
            "4️⃣ افتح موقع <code>www.ivasms.com/login</code> وسجل دخولك حتى تفتح لوحة التحكم.\n"
            "5️⃣ اضغط على (⋮) ← ثم <b>Extensions (الإضافات)</b> وافتح <b>Cookie-Editor</b>.\n"
            "6️⃣ اضغط <b>Export</b> واخرجه بصيغة <b>JSON</b> أو <b>Netscape</b>.\n"
            "7️⃣ ارجع للبوت وارفع الملف أو الصق النص هنا مباشرة 👇"
        )
        try:
            bot.edit_message_text(guide_phone, chat_id, msg_id, reply_markup=mar, parse_mode="HTML")
        except Exception:
            pass
        bot.answer_callback_query(call.id)

def receive_new_cookies_enhanced(message):
    if not is_admin(message.from_user.id):
        return

    # التحقق من الإلغاء
    if message.text and message.text.strip().lower() in ["الغاء", "إلغاء", "/cancel", "cancel"]:
        bot.reply_to(
            message,
            "❌ <b>تم إلغاء عملية تحديث الكوكيز.</b>",
            reply_markup=build_cookies_panel_markup(),
            parse_mode="HTML"
        )
        return

    raw_content = None

    # حالة رفع ملف مستند (.txt أو .json)
    if message.document:
        try:
            file_info = bot.get_file(message.document.file_id)
            if message.document.file_size > 2 * 1024 * 1024:
                bot.reply_to(message, "⚠️ حجم الملف كبير جداً. يرجى إرسال ملف كوكيز نصي صالح.")
                return
            downloaded = bot.download_file(file_info.file_path)
            raw_content = downloaded.decode('utf-8', errors='ignore')
        except Exception as e:
            bot.reply_to(message, f"❌ تعذر تحميل وقراءة الملف: {e}")
            return
    elif message.text:
        raw_content = message.text
    else:
        bot.reply_to(message, "⚠️ يرجى إرسال ملف .txt أو كود JSON صالح للكوكيز.")
        bot.register_next_step_handler(message, receive_new_cookies_enhanced)
        return

    wait_msg = bot.reply_to(
        message,
        "⏳ <b>جاري تحليل الكوكيز وفحص الاتصال بالموقع وتجربة بصمات Yandex والهاتف والكمبيوتر...</b>\nيرجى الانتظار بضع ثوانٍ.",
        parse_mode="HTML"
    )

    def _process_cookies():
        try:
            parsed_cookies = parse_cookies_input(raw_content)
        except ValueError as ve:
            err_text = f"❌ <b>خطأ في صيغة الكوكيز:</b>\n{str(ve)}"
            mar = types.InlineKeyboardMarkup([[
                types.InlineKeyboardButton("🔄 إعادة المحاولة", callback_data="cookies_send", style='primary'),
                types.InlineKeyboardButton("🔙 لوحة الكوكيز", callback_data="admin_cookies_panel", style='danger')
            ]])
            try:
                bot.edit_message_text(err_text, wait_msg.chat.id, wait_msg.message_id, reply_markup=mar, parse_mode="HTML")
            except Exception:
                bot.reply_to(message, err_text, reply_markup=mar, parse_mode="HTML")
            return
        except Exception as ex:
            err_text = f"❌ حدث خطأ أثناء قراءة الكوكيز: {ex}"
            try:
                bot.edit_message_text(err_text, wait_msg.chat.id, wait_msg.message_id, parse_mode="HTML")
            except Exception:
                bot.reply_to(message, err_text)
            return

        # استخراج User-Agent مخصص لو تم إرساله في النص
        custom_ua = None
        for line in raw_content.splitlines():
            l_str = line.strip()
            if l_str.lower().startswith("user-agent:"):
                custom_ua = l_str.split(":", 1)[1].strip()
                break
            elif "Mozilla/5.0" in l_str and " " in l_str and not l_str.startswith("{") and not l_str.startswith("["):
                custom_ua = l_str
                break

        # فحص الكوكيز مباشرة مع الموقع بتجربة البصمات
        res = verify_and_test_cookies(parsed_cookies, preferred_ua=custom_ua)
        if len(res) == 4:
            ok, test_msg, csrf_token, matched_hdrs = res
        else:
            ok, test_msg, csrf_token = res[:3]
            matched_hdrs = None

        if ok:
            # تطبيق الكوكيز وحفظها رسمياً بالبصمة المتطابقة
            apply_cookies(parsed_cookies, csrf_token=csrf_token, custom_headers=matched_hdrs)
            success_text = (
                "🎉 <b>تأكيد: تم فحص وتثبيت الكوكيز بنجاح تام! 🟢</b>\n\n"
                "• <b>الاتصال بالموقع:</b> متصل بنجاح (HTTP 200 OK) ✅\n"
                "• <b>تجاوز الحماية:</b> تم التحقق وتخطي Cloudflare بنجاح ✅\n"
                "• <b>رمز الأمان CSRF:</b> تم استخراجه والتحقق منه ✅\n"
                "• <b>بوابة جلب الرسائل (getsms):</b> استجابة نشطة 200 OK ✅\n"
                f"• <b>عدد الكوكيز المفعلة:</b> <code>{len(parsed_cookies)}</code>\n"
                "• <b>ملف التخزين:</b> <code>mafia_ck_4235.json</code> ✅\n\n"
                "🚀 <b>الكوكيز تعمل الآن بنسبة 100% والبوت يراقب الرسائل فورياً.</b>\n"
                "يمكنك الضغط أدناه لتجربة سحب رسائل قديمة فوراً لتأكيد السحب 👇"
            )
            mar = types.InlineKeyboardMarkup(row_width=1)
            mar.add(
                types.InlineKeyboardButton("🧪 اختبار سحب رسائل قديمة الآن", callback_data="test_old_pull_start", style='success'),
                types.InlineKeyboardButton("🔍 فحص الكوكيز الحالية", callback_data="cookies_check_now", style='primary'),
                types.InlineKeyboardButton("🔙 لوحة الكوكيز", callback_data="admin_cookies_panel", style='danger')
            )
            try:
                bot.edit_message_text(success_text, wait_msg.chat.id, wait_msg.message_id, reply_markup=mar, parse_mode="HTML")
            except Exception:
                bot.reply_to(message, success_text, reply_markup=mar, parse_mode="HTML")
        else:
            fail_text = (
                "❌ <b>فشل فحص الكوكيز مع موقع iVasms!</b>\n\n"
                f"• <b>السبب:</b> {test_msg}\n\n"
                "🛡️ <b>أمان النظام:</b> لم يتم تعديل أو مسح الكوكيز القديمة لحمايتك.\n\n"
                "💡 <b>نصيحة:</b> تأكد من فتح صفحة <code>/portal/sms/received</code> داخل المتصفح والتأكد من أنها تفتح معك بدون Cloudflare challenge، ثم قم بتصدير الكوكيز فوراً."
            )
            mar = types.InlineKeyboardMarkup([[
                types.InlineKeyboardButton("🔄 إعادة المحاولة", callback_data="cookies_send", style='primary'),
                types.InlineKeyboardButton("🔙 لوحة الكوكيز", callback_data="admin_cookies_panel", style='danger')
            ]])
            try:
                bot.edit_message_text(fail_text, wait_msg.chat.id, wait_msg.message_id, reply_markup=mar, parse_mode="HTML")
            except Exception:
                bot.reply_to(message, fail_text, reply_markup=mar, parse_mode="HTML")

    threading.Thread(target=_process_cookies, daemon=True).start()

def handle_test_old_pull_date(message):
    if not is_admin(message.from_user.id):
        return

    text = message.text.strip() if message.text else ""
    if not text or text.lower() in ["الغاء", "إلغاء", "/cancel", "cancel"]:
        bot.reply_to(
            message,
            "❌ <b>تم إلغاء عملية اختبار السحب.</b>",
            reply_markup=build_cookies_panel_markup(),
            parse_mode="HTML"
        )
        return

    # استخراج التاريخ
    start_date_str = None
    if text in ["الافتراضي", "default", "افتراضي"]:
        start_date_str = "01/01/2026"
    else:
        for fmt in ('%d/%m/%Y', '%Y-%m-%d', '%m/%d/%Y', '%d-%m-%Y', '%Y/%m/%d'):
            try:
                dt = datetime.strptime(text, fmt)
                start_date_str = dt.strftime('%m/%d/%Y')
                break
            except ValueError:
                pass

    if not start_date_str:
        mar = types.InlineKeyboardMarkup([[
            types.InlineKeyboardButton("🔄 إعادة المحاولة", callback_data="test_old_pull_start", style='primary'),
            types.InlineKeyboardButton("🔙 لوحة الكوكيز", callback_data="admin_cookies_panel", style='danger')
        ]])
        bot.reply_to(
            message,
            "❌ <b>صيغة التاريخ غير صحيحة!</b>\n\n"
            "يرجى إرسال التاريخ بالصيغة: <code>01/01/2026</code> أو <code>2026-01-01</code>\n"
            "أو إرسال كلمة: <code>الافتراضي</code>",
            reply_markup=mar,
            parse_mode="HTML"
        )
        return

    wait_msg = bot.reply_to(
        message,
        f"⏳ <b>جاري بدء السحب التجريبي...</b>\n"
        f"• تاريخ البداية: <code>{start_date_str}</code>\n"
        "جاري الاتصال بـ iVasms وسحب الرسائل وإرسالها للمجموعة، يرجى الانتظار...",
        parse_mode="HTML"
    )

    def _execute_old_pull():
        try:
            saved = load_cookies_from_file()
            if not saved:
                err_text = "❌ لم يتم العثور على كوكيز محفوظة! قم برفع الكوكيز أولاً."
                try:
                    bot.edit_message_text(err_text, wait_msg.chat.id, wait_msg.message_id, parse_mode="HTML")
                except Exception:
                    bot.reply_to(message, err_text)
                return

            session = requests.Session()
            session.headers.update({
                'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Referer': 'https://www.ivasms.com/portal/sms/received',
                'X-Requested-With': 'XMLHttpRequest'
            })
            if isinstance(saved, list):
                for c in saved:
                    domain = c.get('domain', 'www.ivasms.com').lstrip('.')
                    session.cookies.set(c['name'], c['value'], domain=domain, path=c.get('path', '/'))
            elif isinstance(saved, dict):
                for k, v in saved.items():
                    session.cookies.set(k, v, domain='www.ivasms.com', path='/')

            base_url = "https://www.ivasms.com"
            resp = session.get(f"{base_url}/portal/sms/received", timeout=25, allow_redirects=True)
            if "login" in resp.url.lower() or resp.status_code != 200:
                err_text = f"❌ فشل الاتصال بالموقع (رمز الاستجابة: {resp.status_code}). الكوكيز قد تكون منتهية."
                try:
                    bot.edit_message_text(err_text, wait_msg.chat.id, wait_msg.message_id, parse_mode="HTML")
                except Exception:
                    bot.reply_to(message, err_text)
                return

            soup = BeautifulSoup(resp.text, 'html.parser')
            csrf_meta = soup.find('meta', {'name': 'csrf-token'})
            csrf = csrf_meta.get('content') if csrf_meta else None
            if not csrf:
                err_text = "❌ تعذر استخراج رمز الأمان CSRF من الموقع."
                try:
                    bot.edit_message_text(err_text, wait_msg.chat.id, wait_msg.message_id, parse_mode="HTML")
                except Exception:
                    bot.reply_to(message, err_text)
                return

            today_str = datetime.now().strftime('%m/%d/%Y')
            r = session.post(
                f"{base_url}/portal/sms/received/getsms",
                data={'from': start_date_str, 'to': today_str, '_token': csrf},
                timeout=25
            )
            soup_summary = BeautifulSoup(r.text, 'html.parser')
            country_groups = [el for el in soup_summary.find_all('div') if 'toggleRange' in el.get('onclick', '')]

            if not country_groups:
                no_msg_text = (
                    f"⚠️ <b>لا توجد رسائل مسجلة في هذا النطاق الزمني!</b>\n\n"
                    f"• من تاريخ: <code>{start_date_str}</code> إلى: <code>{today_str}</code>\n"
                    "حسابك لا يحتوي على رسائل في هذه الفترة، جرب تاريخاً أقدم أو كلمة <code>الافتراضي</code>."
                )
                mar = types.InlineKeyboardMarkup([[
                    types.InlineKeyboardButton("🔄 تجربة تاريخ آخر", callback_data="test_old_pull_start", style='primary'),
                    types.InlineKeyboardButton("🔙 لوحة الكوكيز", callback_data="admin_cookies_panel", style='danger')
                ]])
                try:
                    bot.edit_message_text(no_msg_text, wait_msg.chat.id, wait_msg.message_id, reply_markup=mar, parse_mode="HTML")
                except Exception:
                    bot.reply_to(message, no_msg_text, reply_markup=mar, parse_mode="HTML")
                return

            fetched_messages = []
            for g in country_groups:
                onclick = g.get('onclick', '')
                m = re.search(r"toggleRange\('([^']+)'\s*,\s*'([^']+)'\)", onclick)
                if not m:
                    continue
                range_id = m.group(1).strip()
                nr = session.post(
                    f"{base_url}/portal/sms/received/getsms/number",
                    data={'start': start_date_str, 'end': today_str, 'range': range_id, '_token': csrf},
                    timeout=25
                )
                nsoup = BeautifulSoup(nr.text, 'html.parser')
                phone_numbers = []
                for el in nsoup.find_all(['div', 'span', 'li', 'a', 'td']):
                    on = el.get('onclick', '')
                    if on:
                        nm = re.search(r"'(\d{7,})'", on)
                        if nm and nm.group(1) not in phone_numbers:
                            phone_numbers.append(nm.group(1))
                    else:
                        txt = el.get_text(strip=True)
                        if re.fullmatch(r'\d{7,15}', txt) and txt not in phone_numbers:
                            phone_numbers.append(txt)

                for phone in phone_numbers:
                    sr = session.post(
                        f"{base_url}/portal/sms/received/getsms/number/sms",
                        data={'start': start_date_str, 'end': today_str, 'Number': phone, 'Range': range_id, '_token': csrf},
                        timeout=25
                    )
                    ssoup = BeautifulSoup(sr.text, 'html.parser')
                    rows = ssoup.select('table tbody tr')
                    for row in rows:
                        msg_div = row.find('div', class_='msg-text')
                        sms_text = msg_div.get_text(separator=' ').strip() if msg_div else ''
                        if not sms_text:
                            continue
                        cols = row.find_all('td')
                        time_val = cols[2].get_text(strip=True) if len(cols) > 2 else '00:00:00'
                        date_str = f"{start_date_str} {time_val}"
                        fetched_messages.append({
                            'phone': phone,
                            'sms': sms_text,
                            'date': date_str,
                            'range': range_id
                        })
                        if len(fetched_messages) >= 10:
                            break
                    if len(fetched_messages) >= 10:
                        break
                if len(fetched_messages) >= 10:
                    break

            if not fetched_messages:
                err_text = "⚠️ تم العثور على المجموعات لكن تعذر قراءة نصوص الرسائل."
                try:
                    bot.edit_message_text(err_text, wait_msg.chat.id, wait_msg.message_id, parse_mode="HTML")
                except Exception:
                    bot.reply_to(message, err_text)
                return

            sent_count = 0
            for m_item in fetched_messages:
                num = clean_number(m_item['phone'])
                sms_t = m_item['sms']
                d_str = m_item['date']
                otp_c = extract_otp(sms_t)
                text_formatted = format_message(d_str, num, sms_t)
                if send_to_telegram_group(text_formatted, otp_c):
                    sent_count += 1
                time.sleep(1.2)

            report_text = (
                "🎉 <b>اكتمل اختبار سحب الرسائل القديمة بنجاح تام! 🟢</b>\n\n"
                f"• <b>التاريخ المطلوب:</b> <code>{start_date_str}</code>\n"
                f"• <b>المجموعات المكتشفة:</b> <code>{len(country_groups)}</code> مجموعة\n"
                f"• <b>الرسائل المسحوبة:</b> <code>{len(fetched_messages)}</code> رسالة\n"
                f"• <b>المرسل للمجموعة:</b> <code>{sent_count}/{len(fetched_messages)}</code> ✅\n"
                f"• <b>المجموعة المستلمة:</b> <code>{CHAT_IDS[0] if CHAT_IDS else 'N/A'}</code>\n\n"
                "🚀 <b>تم إرسال الرسائل بتنسيق Raven وأزرار النسخ والروابط للمجموعة بنجاح.</b>"
            )
            mar = types.InlineKeyboardMarkup(row_width=1)
            mar.add(
                types.InlineKeyboardButton("🔄 اختبار تاريخ آخر", callback_data="test_old_pull_start", style='primary'),
                types.InlineKeyboardButton("🔙 لوحة الكوكيز", callback_data="admin_cookies_panel", style='danger')
            )
            try:
                bot.edit_message_text(report_text, wait_msg.chat.id, wait_msg.message_id, reply_markup=mar, parse_mode="HTML")
            except Exception:
                bot.reply_to(message, report_text, reply_markup=mar, parse_mode="HTML")

        except Exception as e:
            traceback.print_exc()
            err_text = f"❌ حدث خطأ أثناء اختبار السحب: {str(e)}"
            try:
                bot.edit_message_text(err_text, wait_msg.chat.id, wait_msg.message_id, parse_mode="HTML")
            except Exception:
                bot.reply_to(message, err_text)

    threading.Thread(target=_execute_old_pull, daemon=True).start()

# ==============================================================================
# 🌐 وحدة إدارة أرقام iVasms التلقائية (لوحة الأدمن)
# ==============================================================================
import ivasms_manager as im

# كاش حفظ بيانات النطاقات المعروضة في البث المباشر
LIVE_RANGES_CACHE = {}

# خريطة أكواد التطبيقات المختصرة
LIVE_APP_MAP = {
    "WS": "WhatsApp",
    "TG": "Telegram",
    "TT": "TikTok",
    "FB": "Facebook",
    "AP": "Apple",
    "GO": "Google",
    "TOP": "TOP",
    "ALL": "All Apps"
}

@bot.callback_query_handler(func=lambda call: call.data == "admin_ivasms_panel")
def admin_ivasms_panel_callback(call):
    if not is_admin(call.from_user.id):
        return
    user_states.pop(call.from_user.id, None)
    lang = get_user_language(call.from_user.id)
    status_info = im.check_ivasms_status()
    status_icon = "🟢" if status_info.get('ok') else "🔴"
    status_msg = status_info.get('message', '')
    nums_count = status_info.get('my_numbers_count', 0)
    combos_count = len(get_all_combos())

    stream_active = is_live_stream_enabled()
    stream_status_text = "🟢 شغال وبث فوري للوجهة" if stream_active else "🔴 متوقف مؤقتاً"
    stream_btn_text = "📡 بث القناة/الجروب: 🟢 شغال (إيقاف)" if stream_active else "📡 بث القناة/الجروب: 🔴 متوقف (تشغيل)"

    live_chat = get_live_stream_chat_id()
    live_chat_display = f"<code>{live_chat}</code>" if live_chat else "<i>لم يتم التعيين بعد (اضغط بالأسفل للتعيين)</i>"

    text = (
        "🌐 <b>إدارة وسحب أرقام iVasms الحية</b>\n\n"
        f"<b>📡 حالة الاتصال:</b> {status_icon} {status_msg}\n"
        f"<b>📡 البث التلقائي:</b> {stream_status_text}\n"
        f"<b>📢/👥 وجهة البث المباشر (قناة أو مجموعة):</b> {live_chat_display}\n"
        f"<b>📊 الأرقام في حسابك بالموقع:</b> <code>{nums_count}</code> رقم\n"
        f"<b>💾 الكومبوهات المحفوظة في البوت:</b> <code>{combos_count}</code> كومبو\n\n"
        "🔥 <b>البث المباشر للأرقام التي تستقبل أكواد الآن:</b>\n"
        "<i>يتم سحب الرسائل وبثها في القناة/المجموعة تلقائياً لحظة بلحظة مثل الموقع ⬇️</i>"
    )

    stream_btn_style = 'danger' if is_live_stream_active() else 'success'
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.row(
        types.InlineKeyboardButton(stream_btn_text, callback_data="ivasms_toggle_livestream", style=stream_btn_style)
    )
    if live_chat:
        markup.row(
            types.InlineKeyboardButton("📢/👥 تغيير القناة أو المجموعة", callback_data="ivasms_set_live_group", style='primary'),
            types.InlineKeyboardButton("❌ إزالة الوجهة", callback_data="ivasms_remove_live_group", style='danger')
        )
    else:
        markup.row(
            types.InlineKeyboardButton("📢/👥 ➕ تعيين قناة أو مجموعة للبث", callback_data="ivasms_set_live_group", style='primary')
        )
    markup.row(
        types.InlineKeyboardButton("🟢 واتساب (WS) • لايف", callback_data="ivasms_live_WS", style='primary'),
        types.InlineKeyboardButton("✈️ تليجرام (TG) • لايف", callback_data="ivasms_live_TG", style='primary')
    )
    markup.row(
        types.InlineKeyboardButton("🎵 تيك توك (TT) • لايف", callback_data="ivasms_live_TT", style='primary'),
        types.InlineKeyboardButton("🔵 فيسبوك (FB) • لايف", callback_data="ivasms_live_FB", style='primary')
    )
    markup.row(
        types.InlineKeyboardButton("🍎 آبل (AP) • لايف", callback_data="ivasms_live_AP", style='primary'),
        types.InlineKeyboardButton("🌐 جوجل (GO) • لايف", callback_data="ivasms_live_GO", style='primary')
    )
    markup.row(
        types.InlineKeyboardButton("🔥 الأكثر نشاطاً عالمياً (Top Worldwide)", callback_data="ivasms_live_TOP", style='primary')
    )
    markup.row(
        types.InlineKeyboardButton("🔄 سحب أرقام حسابي الحالية", callback_data="ivasms_sync_all", style='success'),
        types.InlineKeyboardButton("📋 أرقامي الحالية بالموقع", callback_data="ivasms_view_mine", style='primary')
    )
    markup.row(
        types.InlineKeyboardButton("🏷️ تخصيص تطبيق لكومبو", callback_data="admin_combo_service_menu", style='primary'),
        types.InlineKeyboardButton("🗑️ إرجاع وحذف كل الأرقام", callback_data="ivasms_confirm_clear", style='danger')
    )
    markup.add(types.InlineKeyboardButton(get_text("admin_btn_back", lang), callback_data="admin_panel", style='danger'))

    try:
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")
    except Exception:
        bot.send_message(call.message.chat.id, text, reply_markup=markup, parse_mode="HTML")

@bot.callback_query_handler(func=lambda call: call.data == "ivasms_toggle_livestream")
def ivasms_toggle_livestream_callback(call):
    if not is_admin(call.from_user.id):
        return
    current = is_live_stream_enabled()
    set_live_stream_enabled(not current)
    new_state = not current
    state_txt = "🟢 تم تشغيل البث المباشر التلقائي بنجاح!" if new_state else "🔴 تم إيقاف البث المباشر التلقائي مؤقتاً."
    bot.answer_callback_query(call.id, state_txt, show_alert=True)
    admin_ivasms_panel_callback(call)

@bot.callback_query_handler(func=lambda call: call.data == "ivasms_set_live_group")
def ivasms_set_live_group_callback(call):
    if not is_admin(call.from_user.id):
        return
    lang = get_user_language(call.from_user.id)
    chat_id = call.message.chat.id
    user_states[call.from_user.id] = "set_live_stream_group"

    current = get_live_stream_chat_id()
    curr_txt = f"\n• <b>الوجهة الحالية:</b> <code>{current}</code>" if current else ""

    text = (
        "<b>📢/👥 تعيين قناة أو مجموعة للبث المباشر (Live Traffic)</b>\n\n"
        "يمكنك استخدام <b>قناة</b> أو <b>مجموعة</b> لبث الرسائل الحية إليها تلقائياً.\n\n"
        "أرسل الآن أحد الخيارات التالية:\n"
        "1️⃣ <b>يوزر القناة/المجموعة العام:</b> مثل <code>@MyLiveChannel</code>\n"
        "2️⃣ <b>رابط القناة:</b> مثل <code>https://t.me/MyLiveChannel</code>\n"
        "3️⃣ <b>المعرف الرقمي (ID):</b> مثل <code>-100xxxxxxxxxx</code>\n"
        "4️⃣ أو ببساطة <b>قم بتوجيه (Forward) أي رسالة</b> من القناة أو المجموعة إلى هنا وسيتعرف عليها البوت فوراً!"
        f"{curr_txt}\n\n"
        "⚠️ <b>ملاحظة هامة:</b> تأكد من إضافة البوت كمشرف (Admin) بصلاحية نشر الرسائل في القناة أو المجموعة أولاً."
    )
    mar = types.InlineKeyboardMarkup([[
        types.InlineKeyboardButton(get_text("btn_back", lang), callback_data="admin_ivasms_panel", style="danger")
    ]])
    try:
        bot.edit_message_text(text, chat_id=chat_id, message_id=call.message.message_id, reply_markup=mar, parse_mode="HTML")
    except Exception:
        bot.send_message(chat_id, text, reply_markup=mar, parse_mode="HTML")
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data == "ivasms_remove_live_group")
def ivasms_remove_live_group_callback(call):
    if not is_admin(call.from_user.id):
        return
    set_live_stream_chat_id("")
    bot.answer_callback_query(call.id, "✅ تم إزالة وجهة البث المباشر بنجاح وتوقيف البث مؤقتاً.", show_alert=True)
    admin_ivasms_panel_callback(call)

@bot.message_handler(func=lambda msg: user_states.get(msg.from_user.id) == "set_live_stream_group")
def process_set_live_stream_group_msg(message):
    if not is_admin(message.from_user.id):
        return
    lang = get_user_language(message.from_user.id)
    raw = ""

    if message.forward_from_chat:
        raw = str(message.forward_from_chat.id)
    elif message.text:
        t = message.text.strip()
        if "t.me/" in t:
            parts = t.split("t.me/")
            sub = parts[1].strip().split("/")[0].split("?")[0]
            if sub:
                raw = f"@{sub}"
        else:
            raw = t

    if not raw:
        return

    target_id = raw
    target_title = "القناة / المجموعة"
    chat_type_label = "وجهة البث"

    try:
        chat_obj = bot.get_chat(raw)
        target_id = str(chat_obj.id)
        target_title = chat_obj.title or (f"@{chat_obj.username}" if chat_obj.username else "قناة/مجموعة")
        if chat_obj.type == "channel":
            chat_type_label = "قناة 📢"
        elif chat_obj.type in ["supergroup", "group"]:
            chat_type_label = "مجموعة 👥"
    except Exception:
        if not (raw.startswith("-100") or raw.startswith("@") or (raw.startswith("-") and raw[1:].isdigit())):
            mar = types.InlineKeyboardMarkup([[
                types.InlineKeyboardButton(get_text("btn_back", lang), callback_data="admin_ivasms_panel", style="danger")
            ]])
            bot.reply_to(
                message,
                "⚠️ <b>المعرف أو الرابط غير صالح!</b>\n"
                "يمكنك إرسال:\n"
                "• يوزر القناة (مثال: <code>@MyChannel</code>)\n"
                "• رابط القناة (مثال: <code>https://t.me/MyChannel</code>)\n"
                "• معرف رقمي (مثال: <code>-1001234567890</code>)\n"
                "• أو توجيه رسالة من القناة للبوت مباشرة.",
                parse_mode="HTML",
                reply_markup=mar
            )
            return

    set_live_stream_chat_id(target_id)
    user_states.pop(message.from_user.id, None)

    # تجربة إرسال رسالة للتأكد من صلاحيات البوت
    test_ok = True
    try:
        bot.send_message(
            target_id,
            "<b>📡 تم ربط هذه الوجهة بنجاح كـ [بث مباشر Live Traffic] لأرقام iVasms!</b>\nسيتم نشر كافة الرسائل والأكواد التجريبية الحية هنا تلقائياً.",
            parse_mode="HTML"
        )
    except Exception as e:
        test_ok = False
        print(f"[LiveStream] تحذير إرسال رسالة اختبار لـ {target_id}: {e}")

    mar = types.InlineKeyboardMarkup([[
        types.InlineKeyboardButton("🔙 العودة للوحة iVasms", callback_data="admin_ivasms_panel", style="danger")
    ]])

    if test_ok:
        succ_txt = (
            f"✅ <b>تم تعيين {chat_type_label} بنجاح!</b>\n\n"
            f"• <b>الاسم:</b> <b>{html_escape(target_title)}</b>\n"
            f"• <b>المعرف:</b> <code>{target_id}</code>\n"
            f"• <b>حالة الاتصال:</b> 🟢 متصل بنجاح (تم إرسال رسالة تأكيد للوجهة).\n\n"
            "سيبدأ البث المباشر بإرسال الرسائل الحية إلى هنا فوراً."
        )
    else:
        succ_txt = (
            f"✅ <b>تم حفظ المعرف:</b> <code>{target_id}</code>\n\n"
            f"⚠️ <i>تنبيه: لم يتمكن البوت من إرسال رسالة تجريبية. يرجى التأكد من إضافة البوت كـ <b>مشرف (Admin)</b> داخل الـ {chat_type_label} ومنحه صلاحية نشر الرسائل.</i>"
        )

    bot.reply_to(message, succ_txt, parse_mode="HTML", reply_markup=mar)

@bot.callback_query_handler(func=lambda call: call.data.startswith("ivasms_live_"))
def ivasms_live_app_callback(call):
    if not is_admin(call.from_user.id):
        return
    app_code = call.data.replace("ivasms_live_", "")
    app_target = LIVE_APP_MAP.get(app_code, "WhatsApp")
    badge = f"[{app_code}]" if app_code != "TOP" else ""
    
    bot.answer_callback_query(call.id, f"⏳ جلب البث المباشر لـ {app_target}...")
    
    mar = types.InlineKeyboardMarkup(row_width=1)

    if app_code == "TOP":
        ok, msg, items = im.get_top_terminations()
        if ok and items:
            text = (
                "🔥 <b>النطاقات الأكثر نشاطاً عالمياً الآن</b>\n\n"
                "<i>⚡ هذه النطاقات تشهد أكبر حركة استقبال رسائل حول العالم في هذه اللحظة:</i>\n\n"
            )
            for idx, t in enumerate(items[:6], 1):
                name = t.get('termination_name', '')
                total = t.get('total', 0)
                tid = t.get('id', '')
                c_code, c_name, flag, short = get_country_details_smart('', name)
                text += f"<b>{idx}.</b> {flag} [{short}] <b>{name}</b> — <code>{total:,}</code> رسالة\n"
                if tid:
                    LIVE_RANGES_CACHE[str(tid)] = {'range_name': name, 'app': 'All Apps'}
                    mar.add(types.InlineKeyboardButton(f"⚡ تفعيل وسحب {name} (100 رقم)", callback_data=f"liveadd_ALL_{tid}", style='success'))
        else:
            text = "❌ تعذر جلب النطاقات الأكثر نشاطاً حالياً."
    else:
        ok, msg, items = im.get_top_ranges_by_app(app_target, limit=10)
        if ok and items:
            text = (
                f"📱 <b>بث مباشر: أرقام {app_target} {badge}</b>\n\n"
                "<i>⚡ النطاقات النشطة التي تستقبل رموز OTP حية الآن في هذه اللحظة:</i>\n\n"
            )
            for idx, r in enumerate(items[:6], 1):
                rg = r.get('range', '')
                tid = r.get('id', '')
                c_name = r.get('country_name', '')
                flag = r.get('flag', '🌍')
                short = r.get('short', 'UN')
                last_time = r.get('last_seen', '')
                test_num = r.get('test_number', '')

                text += f"<b>{idx}.</b> {flag} <b>[{short}] {rg}</b>\n"
                text += f"   • آخر كود: <code>{last_time}</code> | رقم تجريبي: <code>+{test_num}</code>\n\n"

                if tid:
                    LIVE_RANGES_CACHE[str(tid)] = {'range_name': rg, 'app': app_target}
                    mar.add(types.InlineKeyboardButton(f"⚡ تفعيل وسحب نطاق {rg} ({app_code})", callback_data=f"liveadd_{app_code}_{tid}", style='success'))
            text += "<i>اضغط على أي زر أدناه لتفعيل وسحب النطاق وربطه بالبوت فوراً!</i>"
        else:
            text = f"ℹ️ لا توجد رسائل نشطة مسجلة لـ <b>{app_target}</b> في هذه الدقيقة بالموقع."

    mar.add(types.InlineKeyboardButton(f"🔄 تحديث البث المباشر لـ {app_target}", callback_data=f"ivasms_live_{app_code}", style="primary"))
    mar.add(types.InlineKeyboardButton("🔙 اختيار تطبيق آخر", callback_data="admin_ivasms_panel", style="danger"))

    try:
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=mar, parse_mode="HTML")
    except Exception:
        bot.send_message(call.message.chat.id, text, reply_markup=mar, parse_mode="HTML")

@bot.callback_query_handler(func=lambda call: call.data.startswith("liveadd_"))
def ivasms_liveadd_callback(call):
    if not is_admin(call.from_user.id):
        return
    parts = call.data.split("_")
    app_code = parts[1]
    tid = parts[2]
    app_target = LIVE_APP_MAP.get(app_code, "All Apps")
    
    cached_info = LIVE_RANGES_CACHE.get(str(tid), {})
    range_name = cached_info.get('range_name', '')

    bot.answer_callback_query(call.id, f"⏳ جاري تفعيل وسحب نطاق {range_name or tid} لـ {app_target}...")

    wait_msg = bot.send_message(
        call.message.chat.id,
        f"⏳ <b>جاري تفعيل النطاق على iVasms وسحب الأرقام وحفظها في البوت لخدمة ({app_target})...</b>",
        parse_mode="HTML"
    )

    def _do_add_and_sync():
        ok, msg, summary = im.add_range_and_sync_to_bot(tid, app_name=app_target, range_name=range_name)
        mar = types.InlineKeyboardMarkup(row_width=1)
        mar.add(
            types.InlineKeyboardButton(f"🔙 العودة لبث {app_target}", callback_data=f"ivasms_live_{app_code}", style="danger"),
            types.InlineKeyboardButton("🌐 لوحة أرقام iVasms", callback_data="admin_ivasms_panel", style="primary")
        )

        if ok and summary:
            c_flag = summary.get('flag', '🌍')
            c_name = summary.get('country_name', '')
            c_short = summary.get('short', '')
            c_code = summary.get('country_code', '')
            count = summary.get('count', 0)
            rg_name = summary.get('range_name', '')
            badge = f"[{app_code}] " if app_code != "ALL" else ""

            res_text = (
                "🎉 <b>تم التفعيل والسحب بنجاح!</b>\n\n"
                f"📌 <b>النطاق:</b> <code>{rg_name}</code>\n"
                f"📱 <b>التطبيق المخصص:</b> <b>{app_target} {badge.strip()}</b>\n"
                f"🌍 <b>الدولة:</b> {c_flag} <b>{c_name}</b> <code>(+{c_code})</code>\n"
                f"📊 <b>حجم النطاق (عدد الأرقام):</b> <code>{count}</code> رقم\n\n"
                "✨ <b>تم ربط الأرقام فوراً بقاعدة بيانات البوت وأصبحت جاهزة للمستخدمين!</b>\n"
                f"🏷️ <i>يظهر زر الدولة للمستخدمين بالشكل: <code>{c_flag} {badge}{c_name}</code></i>"
            )
        else:
            res_text = f"❌ <b>فشلت العملية:</b>\n\n{msg}"

        try:
            bot.edit_message_text(res_text, wait_msg.chat.id, wait_msg.message_id, reply_markup=mar, parse_mode="HTML")
        except Exception:
            bot.send_message(call.message.chat.id, res_text, reply_markup=mar, parse_mode="HTML")

    threading.Thread(target=_do_add_and_sync, daemon=True).start()

@bot.callback_query_handler(func=lambda call: call.data == "ivasms_sync_all")
def ivasms_sync_all_callback(call):
    if not is_admin(call.from_user.id):
        return
    lang = get_user_language(call.from_user.id)
    bot.answer_callback_query(call.id, "⏳ جاري مزامنة وسحب الأرقام من الموقع...")

    wait_msg = bot.send_message(call.message.chat.id, "⏳ <b>جاري الاتصال بـ iVasms وسحب الأرقام وإضافتها للكومبو...</b>", parse_mode="HTML")
    
    def _do_sync():
        ok, msg, summary = im.sync_numbers_to_bot_combos()
        mar = types.InlineKeyboardMarkup()
        mar.add(types.InlineKeyboardButton("🔙 لوحة أرقام iVasms", callback_data="admin_ivasms_panel", style="danger"))

        if ok and summary:
            detail_lines = []
            for c_code, count in summary.items():
                c_info = COUNTRY_CODES.get(c_code)
                if c_info:
                    c_name, c_flag, c_short = c_info
                else:
                    _, c_name, c_flag, c_short = get_country_details_smart(c_code)
                detail_lines.append(f"• {c_flag} <b>{c_name} [{c_short}] (+{c_code}):</b> <code>{count}</code> رقم")
            
            res_text = (
                "🎉 <b>تم اكتمال المزامنة بنجاح</b>\n\n"
                f"{msg}\n\n"
                "<b>📋 تفاصيل الأرقام المضافة في الكومبو:</b>\n" +
                "\n".join(detail_lines) + "\n\n"
                "✨ <i>الأرقام أصبحت متاحة ومحدثة فوراً لجميع مستخدمي البوت!</i>"
            )
        elif ok:
            res_text = f"ℹ️ <b>تنبيه:</b> {msg}\n\nيرجى تفعيل نطاقات من البث المباشر أولاً ثم إعادة المزامنة."
        else:
            res_text = f"❌ <b>فشلت المزامنة:</b>\n{msg}"

        try:
            bot.edit_message_text(res_text, wait_msg.chat.id, wait_msg.message_id, reply_markup=mar, parse_mode="HTML")
        except Exception:
            bot.send_message(call.message.chat.id, res_text, reply_markup=mar, parse_mode="HTML")

    threading.Thread(target=_do_sync, daemon=True).start()

@bot.callback_query_handler(func=lambda call: call.data == "ivasms_view_mine")
def ivasms_view_mine_callback(call):
    if not is_admin(call.from_user.id):
        return
    bot.answer_callback_query(call.id, "⏳ جاري جلب أرقام حسابك...")
    ok, msg, numbers = im.get_all_my_numbers()
    mar = types.InlineKeyboardMarkup()
    mar.add(types.InlineKeyboardButton("🔙 لوحة أرقام iVasms", callback_data="admin_ivasms_panel", style="danger"))

    if not ok:
        text = f"❌ {msg}"
    elif not numbers:
        text = "ℹ️ <b>حسابك لا يحتوي على أي أرقام مضافة حالياً في الموقع.</b>\n\nيمكنك استخدام أزرار [البث المباشر للتطبيقات] لتفعيل وسحب أرقام فوراً."
    else:
        sample_lines = []
        for i, item in enumerate(numbers[:15], 1):
            sample_lines.append(f"{i}. <code>+{item['number']}</code> ({item['range_name']}) - ${item['rate']}")
        
        text = (
            f"📋 <b>أرقامك الحالية في iVasms ({len(numbers)} رقم)</b>\n\n" +
            "\n".join(sample_lines) +
            (f"\n\n<i>... وباقي {len(numbers) - 15} رقماً أخرى مسجلة بحسابك.</i>" if len(numbers) > 15 else "")
        )
    try:
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=mar, parse_mode="HTML")
    except Exception:
        bot.send_message(call.message.chat.id, text, reply_markup=mar, parse_mode="HTML")

@bot.callback_query_handler(func=lambda call: call.data == "ivasms_confirm_clear")
def ivasms_confirm_clear_callback(call):
    if not is_admin(call.from_user.id):
        return
    mar = types.InlineKeyboardMarkup(row_width=1)
    mar.add(
        types.InlineKeyboardButton("⚠️ نعم، تأكيد إرجاع وحذف جميع الأرقام", callback_data="ivasms_do_clear_all", style="danger"),
        types.InlineKeyboardButton("🔙 إلغاء وتراجع", callback_data="admin_ivasms_panel", style="primary")
    )
    text = (
        "<b>⚠️ تحذير أمني هام!</b>\n\n"
        "هل أنت متأكد تماماً من رغبتك في:\n"
        "1. إرجاع وحذف <b>كافة الأرقام</b> من حسابك في موقع iVasms؟\n"
        "2. تفريغ وحذف جميع الكومبوهات المحفوظة في البوت؟\n\n"
        "<i>هذا الإجراء لا يمكن التراجع عنه.</i>"
    )
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=mar, parse_mode="HTML")

@bot.callback_query_handler(func=lambda call: call.data == "ivasms_do_clear_all")
def ivasms_do_clear_all_callback(call):
    if not is_admin(call.from_user.id):
        return
    bot.answer_callback_query(call.id, "⏳ جاري إرجاع الأرقام...")
    ok, msg = im.return_all_numbers_from_system()
    mar = types.InlineKeyboardMarkup()
    mar.add(types.InlineKeyboardButton("🔙 لوحة أرقام iVasms", callback_data="admin_ivasms_panel", style="danger"))
    bot.edit_message_text(msg, call.message.chat.id, call.message.message_id, reply_markup=mar, parse_mode="HTML")

# ======================
# 🏷️ إدارة وتخصيص تطبيقات الكومبو للأدمن
# ======================
@bot.callback_query_handler(func=lambda call: call.data == "admin_combo_service_menu")
def admin_combo_service_menu_callback(call):
    if not is_admin(call.from_user.id):
        return
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT country_code, combo_index, service FROM combos ORDER BY country_code, combo_index")
    rows = c.fetchall()
    conn.close()

    if not rows:
        bot.answer_callback_query(call.id, "⚠️ لا توجد كومبوهات حالياً في البوت.", show_alert=True)
        return

    markup = types.InlineKeyboardMarkup(row_width=1)
    for c_code, c_idx, svc in rows:
        name, flag, short = COUNTRY_CODES.get(c_code, ("Unknown", "🌍", "UN"))
        current_svc = svc or "All Apps"
        btn_text = f"{flag} [{short}] {name} (#{c_idx}) ➔ {current_svc}"
        markup.add(types.InlineKeyboardButton(btn_text, callback_data=f"set_svc_pick_{c_code}_{c_idx}", style='primary'))

    markup.add(types.InlineKeyboardButton("🔙 رجوع للوحة الإدارة", callback_data="admin_panel", style="danger"))
    text = (
        "🏷️ <b>تخصيص تطبيق لكل كومبو</b>\n\n"
        "اضغط على أي دولة/كومبو لتحديد التطبيق الخاص به (واتساب، تيك توك، إلخ) أو جعله لجميع التطبيقات.\n\n"
        "<i>📌 سينعكس اسم التطبيق فوراً على زر الدولة وفي رسالة تفاصيل الرقم للمستخدم.</i>"
    )
    try:
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")
    except Exception:
        bot.send_message(call.message.chat.id, text, reply_markup=markup, parse_mode="HTML")

@bot.callback_query_handler(func=lambda call: call.data.startswith("set_svc_pick_"))
def admin_set_svc_pick_callback(call):
    if not is_admin(call.from_user.id):
        return
    parts = call.data.split("_")
    c_code = parts[3]
    c_idx = int(parts[4])
    name, flag, short = COUNTRY_CODES.get(c_code, ("Unknown", "🌍", "UN"))
    current_svc = get_combo_service(c_code, c_idx)

    markup = types.InlineKeyboardMarkup(row_width=2)
    apps = [
        ("🟢 WhatsApp", "WhatsApp"),
        ("✈️ Telegram", "Telegram"),
        ("🎵 TikTok", "TikTok"),
        ("🔵 Facebook", "Facebook"),
        ("🍎 Apple", "Apple"),
        ("🌐 جميع التطبيقات", "All Apps")
    ]
    app_buttons = [types.InlineKeyboardButton(label, callback_data=f"do_set_svc_{c_code}_{c_idx}_{val}", style='primary') for label, val in apps]
    for i in range(0, len(app_buttons), 2):
        markup.row(*app_buttons[i:i+2])
    markup.add(types.InlineKeyboardButton("🔙 رجوع لقائمة الكومبوهات", callback_data="admin_combo_service_menu", style="danger"))

    text = (
        f"<b>🏷️ اختر التطبيق المخصص لـ {flag} [{short}] {name} (#{c_idx}):</b>\n\n"
        f"• <b>التطبيق الحالي:</b> <code>{current_svc}</code>\n\n"
        "اختر التطبيق المطلوب من القائمة أدناه ⬇️"
    )
    try:
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")
    except Exception:
        bot.send_message(call.message.chat.id, text, reply_markup=markup, parse_mode="HTML")

@bot.callback_query_handler(func=lambda call: call.data.startswith("do_set_svc_"))
def admin_do_set_svc_callback(call):
    if not is_admin(call.from_user.id):
        return
    parts = call.data.split("_")
    c_code = parts[3]
    c_idx = int(parts[4])
    app_val = "_".join(parts[5:])

    set_combo_service(c_code, c_idx, app_val)
    name, flag, short = COUNTRY_CODES.get(c_code, ("Unknown", "🌍", "UN"))
    bot.answer_callback_query(call.id, f"✅ تم تعيين التطبيق ({app_val}) لـ {name}!", show_alert=True)
    admin_combo_service_menu_callback(call)

# ======================
# ▶️ تشغيل البوت التفاعلي في خيط منفصل
# ======================
def run_bot():
    print("[*] Starting bot...")
    while True:
        try:
            bot.polling(none_stop=True, timeout=30)
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"[!] Polling error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    threading.Thread(target=main_loop, daemon=True).start()
    threading.Thread(target=live_stream_worker, daemon=True).start()
    threading.Thread(target=hourly_group_reminder_worker, daemon=True).start()
    run_bot()
