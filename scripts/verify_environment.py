#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/verify_environment.py
Verifies runtime dependencies, Python version, file permissions, and environment setup.
"""

import sys
import os
import sqlite3

def check_python_version():
    required_major, required_minor = 3, 10
    current = sys.version_info
    print(f"[+] Python Version: {current.major}.{current.minor}.{current.micro}", end=" ")
    if current.major < required_major or (current.major == required_major and current.minor < required_minor):
        print(f"❌ (Requires Python {required_major}.{required_minor}+)")
        return False
    print("✅")
    return True

def check_packages():
    required = [
        ("telebot", "pyTelegramBotAPI"),
        ("requests", "requests"),
        ("bs4", "beautifulsoup4"),
        ("lxml", "lxml"),
    ]
    all_ok = True
    for mod_name, pkg_name in required:
        try:
            __import__(mod_name)
            print(f"[+] Package '{pkg_name}': Installed ✅")
        except ImportError:
            print(f"[!] Package '{pkg_name}': NOT found ❌ (Run: pip install -r requirements.txt)")
            all_ok = False
    return all_ok

def check_sqlite():
    try:
        conn = sqlite3.connect(":memory:")
        c = conn.cursor()
        c.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, val TEXT)")
        c.execute("INSERT INTO test (val) VALUES (?)", ("ok",))
        res = c.execute("SELECT val FROM test").fetchone()
        conn.close()
        if res and res[0] == "ok":
            print("[+] SQLite Engine: Operational ✅")
            return True
        return False
    except Exception as e:
        print(f"[!] SQLite Engine: Error ({e}) ❌")
        return False

def check_files():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    essential_files = [
        "main.py",
        "country_data.py",
        "locales.py",
        "ivasms_manager.py",
        "requirements.txt",
        "LICENSE"
    ]
    all_ok = True
    for fname in essential_files:
        fpath = os.path.join(base_dir, fname)
        if os.path.isfile(fpath):
            print(f"[+] Essential file '{fname}': Present ✅")
        else:
            print(f"[!] Essential file '{fname}': Missing ❌")
            all_ok = False
    return all_ok

def main():
    print("==================================================")
    print(" RAVEN BOT X - Environment Verification")
    print("==================================================")
    r1 = check_python_version()
    r2 = check_packages()
    r3 = check_sqlite()
    r4 = check_files()
    print("--------------------------------------------------")
    if all([r1, r2, r3, r4]):
        print("🎉 Environment verification PASSED. Ready to run.")
        sys.exit(0)
    else:
        print("⚠️ Environment verification found issues. Please review above.")
        sys.exit(1)

if __name__ == "__main__":
    main()
