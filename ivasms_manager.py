#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
ivasms_manager.py - وحدة إدارة ومزامنة أرقام iVasms تلقائياً
================================================================================
موديول مستقل يوفر:
1. مزامنة وسحب أرقام الحساب وتخزينها في قاعدة بيانات البوت (combos).
2. البحث في مستودع الموقع العالمي عن الدول المتاحة وأسعارها وإضافة نطاقات جديدة.
3. إرجاع وحذف الأرقام المنتهية من الموقع وقاعدة بيانات البوت.
4. فحص الجلسة والكوكيز واستخراج رمز الأمان CSRF تلقائياً.
"""

import os
import re
import json
import sqlite3
import requests
from bs4 import BeautifulSoup
from datetime import datetime

BASE_URL = "https://www.ivasms.com"
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bot1.db")
COOKIES_JSON = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mafia_ck_4235.json")

def find_latest_cookie_txt():
    """البحث عن أحدث ملف كوكيز تم تحميله في مجلد Downloads"""
    import glob
    candidates = glob.glob("/home/obs/Downloads/*cookie*.txt")
    if not candidates:
        return None
    candidates.sort(key=os.path.getmtime, reverse=True)
    return candidates[0]

COOKIES_TXT = find_latest_cookie_txt()

# استيراد خريطة الدول والدوال الذكية من country_data
from country_data import COUNTRY_CODES, get_country_details_smart, get_app_badge, get_service_display

# للتوافقية السابقة
COUNTRY_CODES_MAP = {k: (v[0], v[1]) for k, v in COUNTRY_CODES.items()}

def get_session():
    """إنشاء جلسة requests متطابقة تماماً مع متصفح Chrome وتعيين الكوكيز"""
    session = requests.Session()
    hdrs = {
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/javascript, */*; q=0.01',
        'Accept-Language': 'en-US,en;q=0.9,ar;q=0.8',
        'sec-ch-ua': '"Chromium";v="152", "Google Chrome";v="152", "Not-A.Brand";v="99"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Linux"',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-origin',
        'X-Requested-With': 'XMLHttpRequest',
    }
    active_headers_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "active_headers.json")
    if os.path.exists(active_headers_file):
        try:
            with open(active_headers_file, 'r', encoding='utf-8') as f:
                saved_hdrs = json.load(f)
                if isinstance(saved_hdrs, dict):
                    for k in ['User-Agent', 'sec-ch-ua', 'sec-ch-ua-mobile', 'sec-ch-ua-platform']:
                        if k in saved_hdrs and saved_hdrs[k]:
                            hdrs[k] = saved_hdrs[k]
        except Exception:
            pass
    hdrs['Accept'] = 'application/json, text/javascript, */*; q=0.01'
    hdrs['X-Requested-With'] = 'XMLHttpRequest'
    session.headers.update(hdrs)

    # 1. فحص أحدث ملف كوكيز نصي تم تحميله في مجلد التنزيلات
    latest_txt = find_latest_cookie_txt()
    if latest_txt and os.path.exists(latest_txt):
        try:
            with open(latest_txt, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    parts = line.split('\t')
                    if len(parts) >= 7:
                        domain = parts[0].lstrip('.')
                        name = parts[5]
                        value = parts[6]
                        path = parts[2]
                        session.cookies.set(name, value, domain=domain, path=path)
                        session.cookies.set(name, value, domain='www.ivasms.com', path=path)
                        session.cookies.set(name, value, domain='.ivasms.com', path=path)
            return session
        except Exception:
            pass

    # 2. فحص ملف JSON
    if os.path.exists(COOKIES_JSON):
        try:
            with open(COOKIES_JSON, 'r', encoding='utf-8') as f:
                cookies = json.load(f)
            for c in cookies:
                domain = c.get('domain', 'www.ivasms.com').lstrip('.')
                session.cookies.set(c['name'], c['value'], domain=domain, path=c.get('path', '/'))
                session.cookies.set(c['name'], c['value'], domain='www.ivasms.com', path=c.get('path', '/'))
                session.cookies.set(c['name'], c['value'], domain='.ivasms.com', path=c.get('path', '/'))
            return session
        except Exception:
            pass

    return None

def get_csrf_token(session=None):
    """استخراج رمز الـ CSRF Token من صفحة اللوحة"""
    if session is None:
        session = get_session()
    if not session:
        return None
    try:
        r = session.get(f"{BASE_URL}/portal/numbers", headers={'Accept': 'text/html'}, timeout=20)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, 'html.parser')
            meta = soup.find('meta', {'name': 'csrf-token'})
            if meta:
                return meta.get('content')
            match = re.search(r'name=["\'](?:_token|csrf-token)["\']\s+value=["\']([^"\']+)["\']', r.text)
            if match:
                return match.group(1)
    except Exception:
        pass
    return None

def check_ivasms_status():
    """فحص حالة الاتصال والحساب، وإرجاع تقرير مختصر"""
    session = get_session()
    if not session:
        return {
            'ok': False,
            'message': '❌ تعذر العثور على ملف الكوكيز.'
        }
    try:
        ajax_headers = {
            'X-Requested-With': 'XMLHttpRequest',
            'Accept': 'application/json, text/javascript, */*; q=0.01'
        }
        r = session.get(f"{BASE_URL}/portal/numbers", params={'draw': 1, 'start': 0, 'length': 1}, headers=ajax_headers, timeout=20)
        if r.status_code == 403:
            return {'ok': False, 'message': '❌ الكوكيز منتهية الصلاحية (403 Cloudflare).'}
        if "login" in r.url.lower():
            return {'ok': False, 'message': '⚠️ تم التحويل لصفحة تسجيل الدخول (الجلسة منتهية).'}
        if r.status_code == 200:
            try:
                data = r.json()
            except Exception:
                if "login" in r.text.lower():
                    return {'ok': False, 'message': '⚠️ تم التحويل لصفحة تسجيل الدخول.'}
                return {'ok': False, 'message': '❌ استجابة غير صالحة من الموقع (تأكد من تجديد الكوكيز).'}
            total_my_numbers = data.get('recordsTotal', 0)
            return {
                'ok': True,
                'status_code': 200,
                'my_numbers_count': total_my_numbers,
                'message': f'🟢 الاتصال نشط | لديك {total_my_numbers} رقم في الحساب.'
            }
        return {'ok': False, 'message': f'❌ استجابة غير متوقعة: {r.status_code}'}
    except Exception as e:
        return {'ok': False, 'message': f'❌ خطأ في الاتصال: {str(e)}'}

def get_all_my_numbers():
    """جلب قائمة بجميع الأرقام المضافة حالياً في حسابك على iVasms"""
    session = get_session()
    if not session:
        return False, "❌ لا توجد جلسة نشطة.", []

    try:
        ajax_headers = {
            'X-Requested-With': 'XMLHttpRequest',
            'Accept': 'application/json, text/javascript, */*; q=0.01'
        }
        # جلب أول 500 رقم
        r = session.get(f"{BASE_URL}/portal/numbers", params={'draw': 1, 'start': 0, 'length': 500}, headers=ajax_headers, timeout=25)
        if r.status_code != 200:
            return False, f"رمز الاستجابة: {r.status_code}", []

        try:
            data = r.json()
        except Exception:
            return False, "تعذر قراءة بيانات الأرقام من الموقع (استجابة غير صالحة).", []

        raw_list = data.get('data', [])
        clean_numbers = []

        for item in raw_list:
            num_val = item.get('Number') or item.get('number') or ''
            num_clean = re.sub(r'<[^>]+>', '', str(num_val)).strip().lstrip('+')
            range_name = item.get('range') or item.get('range_name') or ''
            rate = item.get('A2P') or item.get('rate') or ''
            
            num_id = item.get('id') or ''
            if not num_id and 'number_id' in item:
                m = re.search(r'value=["\'](\d+)["\']', str(item.get('number_id')))
                if m:
                    num_id = m.group(1)

            if num_clean and num_clean.isdigit():
                clean_numbers.append({
                    'id': num_id,
                    'number': num_clean,
                    'range_name': range_name,
                    'rate': rate
                })

        return True, "تم الجلب بنجاح", clean_numbers
    except Exception as e:
        return False, f"خطأ: {str(e)}", []

def sync_numbers_to_bot_combos(default_service="All Apps"):
    """سحب جميع الأرقام من iVasms وإضافتها مباشرة إلى جدول combos في bot1.db مع ربط التطبيق"""
    ok, msg, numbers_list = get_all_my_numbers()
    if not ok:
        return False, msg, {}

    if not numbers_list:
        return True, "حسابك لا يحتوي على أي أرقام حالياً لسحبها.", {}

    # تصنيف الأرقام حسب كود الدولة باستخدام get_country_details_smart
    grouped = {}
    for item in numbers_list:
        num = item['number']
        rg_name = item.get('range_name', '')
        c_code, c_name, flag, short = get_country_details_smart(num, rg_name)

        if c_code not in grouped:
            grouped[c_code] = {'numbers': [], 'name': c_name, 'flag': flag, 'short': short}
        if num not in grouped[c_code]['numbers']:
            grouped[c_code]['numbers'].append(num)

    # حفظ الأرقام في bot1.db
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        saved_summary = {}

        for c_code, info in grouped.items():
            nums = info['numbers']
            # البحث عن أقصى combo_index
            c.execute("SELECT MAX(combo_index) FROM combos WHERE country_code=?", (c_code,))
            res = c.fetchone()[0]
            next_index = 1 if res is None else res + 1

            nums_json = json.dumps(nums, ensure_ascii=False)
            c.execute("INSERT INTO combos (country_code, combo_index, numbers, service) VALUES (?, ?, ?, ?)",
                      (c_code, next_index, nums_json, default_service))
            saved_summary[c_code] = len(nums)

        conn.commit()
        conn.close()
        return True, f"✅ تم سحب {len(numbers_list)} رقماً وتخزينها بنجاح!", saved_summary
    except Exception as e:
        return False, f"❌ خطأ أثناء الحفظ في قاعدة البيانات: {str(e)}", {}

def search_test_numbers(country_query, limit=10):
    """البحث في مستودع الأرقام العالمي عن دولة أو نطاق معين"""
    session = get_session()
    if not session:
        return False, "❌ لا توجد جلسة نشطة.", []

    query = str(country_query).strip().lstrip('+')
    try:
        # البحث باستخدام DataTables search
        params = {
            'draw': 1,
            'start': 0,
            'length': limit,
            'search[value]': query
        }
        r = session.get(f"{BASE_URL}/portal/numbers/test", params=params, timeout=25)
        if r.status_code != 200:
            return False, f"رمز الاستجابة: {r.status_code}", []

        data = r.json()
        records = data.get('data', [])
        results = []

        for row in records:
            range_name = row.get('range', '')
            test_num = row.get('test_number', '')
            rate = row.get('A2P', '')
            term = row.get('term', '')
            row_id = row.get('id', '')

            # فلترة النتائج للتأكد من تطابق الاستعلام
            if query.lower() in range_name.lower() or query in test_num or query in str(row_id):
                results.append({
                    'id': row_id,
                    'range': range_name,
                    'test_number': test_num,
                    'rate': rate,
                    'term': term
                })

        # إذا كانت الفلترة الصارمة فارغة، أعد السجلات كما أرجعها السيرفر
        if not results and records:
            for row in records[:limit]:
                results.append({
                    'id': row.get('id'),
                    'range': row.get('range'),
                    'test_number': row.get('test_number'),
                    'rate': row.get('A2P'),
                    'term': row.get('term')
                })

        return True, f"تم العثور على {len(results)} نطاقاً متاحاً.", results
    except Exception as e:
        return False, f"❌ خطأ في البحث: {str(e)}", []

def add_range_to_account(range_id):
    """إضافة نطاق أرقام إلى حسابك في iVasms برمجياً بنقرة واحدة"""
    session = get_session()
    if not session:
        return False, "❌ لا توجد جلسة نشطة."

    csrf = get_csrf_token(session)
    if not csrf:
        return False, "❌ تعذر استخراج رمز CSRF Token."

    url = f"{BASE_URL}/portal/numbers/termination/number/add"
    payload = {
        'id': str(range_id),
        '_token': csrf
    }
    headers = {
        'Referer': f"{BASE_URL}/portal/numbers/test",
        'Origin': BASE_URL,
        'X-CSRF-TOKEN': csrf,
        'X-Requested-With': 'XMLHttpRequest'
    }

    try:
        resp = session.post(url, data=payload, headers=headers, timeout=25)
        if resp.status_code == 200:
            res_json = resp.json()
            msg = res_json.get('message', 'تمت إضافة الأرقام بنجاح!')
            return True, msg
        else:
            return False, f"فشل الطلب برمز: {resp.status_code}"
    except Exception as e:
        return False, f"خطأ أثناء الإضافة: {str(e)}"

def return_all_numbers_from_system():
    """إرجاع كافة الأرقام وحذفها من حساب iVasms ومن قاعدة بيانات البوت"""
    session = get_session()
    if not session:
        return False, "❌ لا توجد جلسة نشطة."

    csrf = get_csrf_token(session)
    if not csrf:
        return False, "❌ تعذر استخراج رمز CSRF Token."

    url = f"{BASE_URL}/portal/numbers/return/allnumber/bluck"
    payload = {'_token': csrf}
    headers = {
        'Referer': f"{BASE_URL}/portal/numbers",
        'Origin': BASE_URL,
        'X-CSRF-TOKEN': csrf,
        'X-Requested-With': 'XMLHttpRequest'
    }

    try:
        resp = session.post(url, data=payload, headers=headers, timeout=30)
        if resp.status_code == 200:
            # تفريغ جدول combos في البوت
            try:
                conn = sqlite3.connect(DB_PATH)
                c = conn.cursor()
                c.execute("DELETE FROM combos")
                conn.commit()
                conn.close()
            except Exception:
                pass
            return True, "✅ تم إرجاع جميع الأرقام للنظام وتفريغ الكومبو بالكامل!"
        return False, f"فشل الإرجاع (رمز: {resp.status_code})"
    except Exception as e:
        return False, f"❌ خطأ أثناء الإرجاع: {str(e)}"

def return_single_number_from_system(number_id):
    """إرجاع رقم واحد محدد للنظام"""
    session = get_session()
    if not session:
        return False, "❌ لا توجد جلسة نشطة."

    csrf = get_csrf_token(session)
    if not csrf:
        return False, "❌ تعذر استخراج رمز CSRF Token."

    url = f"{BASE_URL}/portal/numbers/return/number/bluck"
    payload = {
        'NumberID[]': [str(number_id)],
        '_token': csrf
    }
    headers = {
        'Referer': f"{BASE_URL}/portal/numbers",
        'Origin': BASE_URL,
        'X-CSRF-TOKEN': csrf,
        'X-Requested-With': 'XMLHttpRequest'
    }

    try:
        resp = session.post(url, data=payload, headers=headers, timeout=25)
        if resp.status_code == 200:
            return True, "✅ تم إرجاع الرقم للنظام بنجاح."
        return False, f"فشل الإرجاع (رمز: {resp.status_code})"
    except Exception as e:
        return False, f"❌ خطأ: {str(e)}"

def get_top_terminations():
    """جلب أكثر النطاقات الشغالة حالياً في لوحة التحكم (Top Ranges)"""
    session = get_session()
    if not session:
        return False, "❌ لا توجد جلسة نشطة.", []
    try:
        r = session.get(f"{BASE_URL}/portal/top_terminations", timeout=20)
        if r.status_code == 200:
            data = r.json()
            items = data.get('data', [])
            return True, f"تم العثور على {len(items)} نطاقاً نشطاً.", items
        return False, f"رمز الاستجابة: {r.status_code}", []
    except Exception as e:
        return False, f"خطأ: {str(e)}", []

def get_top_ranges_by_app(app_name, limit=25):
    """جلب النطاقات والدول التي تستقبل رسائل حالياً لتطبيق معين (WhatsApp, TikTok, إلخ) مع تفاصيل الدولة الذكية"""
    session = get_session()
    if not session:
        return False, "❌ لا توجد جلسة نشطة.", []
    try:
        r = session.get(
            f"{BASE_URL}/portal/sms/test/sms",
            params={'app': app_name, 'draw': 1, 'start': 0, 'length': limit},
            timeout=25
        )
        if r.status_code == 200:
            data = r.json()
            rows = data.get('data', [])
            active_ranges = {}
            for row in rows:
                range_name = str(row.get('range') or '').strip()
                term_id = row.get('termination_id', '')
                time_str = str(row.get('senttime') or '')
                
                term_obj = row.get('termination') or {}
                test_num_raw = term_obj.get('test_number', '')
                test_number = re.sub(r'<[^>]+>', '', str(test_num_raw)).strip().lstrip('+')

                if range_name and range_name not in active_ranges:
                    c_code, c_name, flag, short = get_country_details_smart(test_number, range_name)
                    time_display = time_str.split()[-1] if time_str else ''
                    
                    active_ranges[range_name] = {
                        'range': range_name,
                        'id': term_id,
                        'last_seen': time_display,
                        'full_time': time_str,
                        'test_number': test_number,
                        'country_code': c_code,
                        'country_name': c_name,
                        'flag': flag,
                        'short': short,
                        'app': app_name
                    }
            results = list(active_ranges.values())
            return True, f"تم العثور على {len(results)} نطاقاً نشطاً لـ {app_name}.", results
        return False, f"رمز الاستجابة: {r.status_code}", []
    except Exception as e:
        return False, f"خطأ: {str(e)}", []

def add_range_and_sync_to_bot(range_id, app_name='WhatsApp', range_name=''):
    """تفعيل النطاق في موقع iVasms وسحب أرقامه فوراً وحفظها في البوت مع ربط التطبيق وحجم الأرقام"""
    session = get_session()
    if not session:
        return False, "❌ لا توجد جلسة نشطة لموقع iVasms.", {}

    # 1. تفعيل النطاق بالموقع
    ok, msg = add_range_to_account(range_id)
    if not ok:
        return False, f"❌ فشل تفعيل النطاق في الموقع: {msg}", {}

    import time
    time.sleep(1.5)

    # 2. جلب أرقام الحساب
    ok_nums, msg_nums, all_nums = get_all_my_numbers()
    if not ok_nums or not all_nums:
        return False, f"⚠️ تم تفعيل النطاق لكن تعذر جلب الأرقام فوراً: {msg_nums}", {}

    # 3. تصفية أرقام النطاق المستهدف
    matched = []
    if range_name:
        matched = [x for x in all_nums if str(x.get('range_name', '')).strip().lower() == range_name.strip().lower()]

    if not matched:
        matched = all_nums

    num_strings = [x['number'] for x in matched]
    if not num_strings:
        return False, "⚠️ لم يتم العثور على أرقام جديدة في حسابك.", {}

    sample_num = num_strings[0]
    c_code, c_name, flag, short = get_country_details_smart(sample_num, range_name)

    # 4. حفظ الكومبو في قاعدة بيانات البوت
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT MAX(combo_index) FROM combos WHERE country_code=?", (c_code,))
        res = c.fetchone()[0]
        next_idx = 1 if res is None else res + 1

        nums_json = json.dumps(num_strings, ensure_ascii=False)
        c.execute("INSERT INTO combos (country_code, combo_index, numbers, service) VALUES (?, ?, ?, ?)",
                  (c_code, next_idx, nums_json, app_name))
        conn.commit()
        conn.close()

        summary = {
            'count': len(num_strings),
            'country_code': c_code,
            'country_name': c_name,
            'flag': flag,
            'short': short,
            'service': app_name,
            'combo_index': next_idx,
            'range_name': range_name or f"{c_name} Range",
            'sample_number': sample_num
        }
        return True, f"✅ تم تفعيل وسحب نطاق {summary['range_name']} ({len(num_strings)} رقم) بنجاح!", summary
    except Exception as e:
        return False, f"❌ خطأ في حفظ الكومبو بالبوت: {str(e)}", {}

def fetch_live_stream_messages(limit=25):
    """
    سحب الرسائل الحية المباشرة من موقع iVasms التي يستقبلها الموقع لحظة بلحظة لجميع التطبيقات
    """
    session = get_session()
    if not session:
        return []

    try:
        import html as _html
        ajax_headers = {
            'X-Requested-With': 'XMLHttpRequest',
            'Accept': 'application/json, text/javascript, */*; q=0.01'
        }
        r = session.get(
            f"{BASE_URL}/portal/sms/test/sms",
            params={'draw': 1, 'start': 0, 'length': limit},
            headers=ajax_headers,
            timeout=15
        )
        if r.status_code != 200:
            return []

        try:
            data = r.json()
        except Exception:
            return []

        rows = data.get('data', [])
        clean_messages = []

        for row in rows:
            msg_id = row.get('id') or row.get('DT_RowId')
            if not msg_id:
                continue

            orig_raw = str(row.get('originator') or '')
            app_match = re.search(r'<p[^>]*>([^<]+)</p>', orig_raw)
            if app_match:
                app_name = app_match.group(1).strip()
            else:
                app_clean = re.sub(r'<script.*?</script>', '', orig_raw, flags=re.DOTALL)
                app_clean = re.sub(r'<[^>]+>', '', app_clean).strip()
                app_name = app_clean if app_clean else "SMS"

            term_obj = row.get('termination') or {}
            test_num_raw = str(term_obj.get('test_number') or '')
            number = re.sub(r'<[^>]+>', '', test_num_raw).strip().lstrip('+')
            if not number:
                continue

            raw_msg = str(row.get('messagedata') or '')
            clean_text = _html.unescape(raw_msg).strip()

            range_name = str(row.get('range') or '').strip()
            sent_time = str(row.get('senttime') or '').strip()

            c_code, c_name, flag, short = get_country_details_smart(number, range_name)

            clean_messages.append({
                'id': str(msg_id),
                'number': number,
                'app': app_name,
                'text': clean_text,
                'range': range_name,
                'time': sent_time,
                'country_code': c_code,
                'country_name': c_name,
                'flag': flag,
                'short': short
            })

        return clean_messages
    except Exception as e:
        print(f"[!] Error fetching live stream: {e}")
        return []
