#!/usr/bin/env python3
import os
import json
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

COOKIES_FILE = "mafia_ck_4235.json"
TARGET_URL = "https://www.ivasms.com/portal/sms/received"
SMS_API_URL = "https://www.ivasms.com/portal/sms/received/getsms"

def test():
    if not os.path.exists(COOKIES_FILE):
        print(f"❌ لم يتم العثور على ملف الكوكيز: {COOKIES_FILE}")
        return

    try:
        with open(COOKIES_FILE, 'r', encoding='utf-8') as f:
            cookies_data = json.load(f)
    except Exception as e:
        print(f"❌ خطأ في قراءة ملف JSON: {e}")
        return

    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    })

    if isinstance(cookies_data, list):
        for c in cookies_data:
            name = c.get('name')
            value = c.get('value')
            domain = c.get('domain', 'www.ivasms.com').lstrip('.')
            session.cookies.set(name, value, domain=domain, path='/')

    print("⏳ جاري اختبار الاتصال باللوحة...")
    try:
        resp = session.get(TARGET_URL, timeout=25, allow_redirects=True)
        print(f"📡 رمز استجابة اللوحة: {resp.status_code}")

        if "login" in resp.url.lower():
            print("⚠️ النتيجة: تم التحويل لصفحة تسجيل الدخول.")
            return
        elif resp.status_code == 200:
            print("✅ تم الدخول إلى لوحة التحكم بنجاح تام!")
            soup = BeautifulSoup(resp.text, 'html.parser')
            csrf = soup.find('meta', {'name': 'csrf-token'})
            csrf_token = csrf.get('content') if csrf else None
            
            if csrf_token:
                print("🔑 تم استخراج رمز الحماية CSRF Token بنجاح.")
                today = datetime.now()
                payload = {
                    'from': (today - timedelta(days=3)).strftime('%m/%d/%Y'),
                    'to': today.strftime('%m/%d/%Y'),
                    '_token': csrf_token
                }
                headers = {
                    'Referer': TARGET_URL,
                    'X-Requested-With': 'XMLHttpRequest'
                }
                api_resp = session.post(SMS_API_URL, headers=headers, data=payload, timeout=25)
                print(f"📩 رد واجهة جلب الرسائل (POST getsms): Status {api_resp.status_code}")
                if api_resp.status_code == 200:
                    print("🎉 النتيجة النهائية: البوت متصل بالموقع وجاهز 100% لسحب أي رسالة SMS فور وصولها!")
            else:
                print("❌ تعذر العثور على CSRF token")

    except requests.exceptions.RequestException as e:
        print(f"❌ خطأ أثناء الاتصال: {e}")

if __name__ == "__main__":
    test()
