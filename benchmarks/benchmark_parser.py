#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
benchmarks/benchmark_parser.py
Measures execution performance of core parsing and transformation functions:
1. OTP Code Extraction (extract_otp)
2. Service Detection (detect_service)
3. Smart Country Resolution (get_country_details_smart)
4. Cookie Parsing (parse_cookies_input)
"""

import time
import statistics
import platform
import json
import sys
import os

# Add root directory to sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from main import extract_otp, detect_service, parse_cookies_input
from country_data import get_country_details_smart

SAMPLE_MESSAGES = [
    "Your WhatsApp code is 482-910. Do not share it with anyone.",
    "Telegram code: 82914. You can also tap on this link to log in.",
    "رمز تحقق الخاص بك هو: 938210 صالح لمدة 5 دقائق",
    "[TikTok] 748291 is your verification code. Valid for 10 minutes.",
    "G-592813 is your Google verification code.",
    "Facebook: 384910 is your confirmation code.",
    "Apple ID Code is: 827419. Don't share it.",
    "Normal customer support inquiry text with no numbers inside.",
]

SAMPLE_NETSCAPE_COOKIES = (
    "# Netscape HTTP Cookie File\n"
    ".ivasms.com\tTRUE\t/\tFALSE\t1788636334\t_fbp\tfb.1.mock_fbp_token_example\n"
    "www.ivasms.com\tFALSE\t/\tTRUE\t1788636334\tcf_clearance\tmock_cf_clearance_sample_for_benchmarking\n"
    "www.ivasms.com\tFALSE\t/\tTRUE\t1788636334\tivas_sms_session\tmock_session_token_sample_for_benchmarking\n"
    "www.ivasms.com\tFALSE\t/\tTRUE\t1788636334\tXSRF-TOKEN\tmock_xsrf_token_sample_for_benchmarking\n"
)

SAMPLE_JSON_COOKIES = json.dumps([
    {"name": "_fbp", "value": "fb.1.mock_fbp_token_example", "domain": ".ivasms.com", "path": "/"},
    {"name": "cf_clearance", "value": "mock_cf_clearance_sample_for_benchmarking", "domain": "www.ivasms.com", "path": "/"},
    {"name": "ivas_sms_session", "value": "mock_session_token_sample_for_benchmarking", "domain": "www.ivasms.com", "path": "/"},
    {"name": "XSRF-TOKEN", "value": "mock_xsrf_token_sample_for_benchmarking", "domain": "www.ivasms.com", "path": "/"},
])

def run_benchmark(name, func, args_list, iterations=10000, warmup=1000):
    # Warmup
    for _ in range(warmup):
        for args in args_list:
            func(*args)

    durations_us = []
    total_ops = iterations * len(args_list)

    t0 = time.perf_counter()
    for _ in range(iterations):
        for args in args_list:
            s = time.perf_counter_ns()
            func(*args)
            e = time.perf_counter_ns()
            durations_us.append((e - s) / 1000.0)
    total_time_s = time.perf_counter() - t0

    mean_us = statistics.mean(durations_us)
    median_us = statistics.median(durations_us)
    min_us = min(durations_us)
    max_us = max(durations_us)
    stdev_us = statistics.stdev(durations_us) if len(durations_us) > 1 else 0.0
    throughput = total_ops / total_time_s

    return {
        "name": name,
        "total_ops": total_ops,
        "total_time_s": total_time_s,
        "mean_us": mean_us,
        "median_us": median_us,
        "min_us": min_us,
        "max_us": max_us,
        "stdev_us": stdev_us,
        "throughput_ops_sec": throughput
    }

def main():
    print("Running benchmarks...")
    
    otp_args = [(m,) for m in SAMPLE_MESSAGES]
    cd_args = [
        ("201001234567", ""),
        ("14155552671", ""),
        ("491761234567", ""),
        ("79123456789", ""),
        ("", "Germany 100 Range"),
        ("", "BANGLADESH 47631"),
        ("9999999999", "")
    ]
    cookie_args = [(SAMPLE_NETSCAPE_COOKIES,), (SAMPLE_JSON_COOKIES,)]

    results = [
        run_benchmark("OTP Extraction (extract_otp)", extract_otp, otp_args, iterations=2000, warmup=500),
        run_benchmark("Service Detection (detect_service)", detect_service, otp_args, iterations=2000, warmup=500),
        run_benchmark("Smart Country Lookup (get_country_details_smart)", get_country_details_smart, cd_args, iterations=2000, warmup=500),
        run_benchmark("Cookie Parsing (parse_cookies_input)", parse_cookies_input, cookie_args, iterations=500, warmup=100),
    ]

    report = {
        "environment": {
            "os": platform.system(),
            "os_release": platform.release(),
            "architecture": platform.machine(),
            "python_version": platform.python_version(),
            "processor": platform.processor() or "x86_64",
        },
        "results": results
    }

    # Save JSON report
    report_json_path = os.path.join(os.path.dirname(__file__), "benchmark_results.json")
    with open(report_json_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    # Save Markdown report
    report_md_path = os.path.join(os.path.dirname(__file__), "REPORT.md")
    with open(report_md_path, "w", encoding="utf-8") as f:
        f.write("# Benchmark Report\n\n")
        f.write("## Environment\n\n")
        f.write(f"- **OS**: {report['environment']['os']} {report['environment']['os_release']}\n")
        f.write(f"- **Architecture**: {report['environment']['architecture']}\n")
        f.write(f"- **Python Version**: {report['environment']['python_version']}\n")
        f.write(f"- **Processor**: {report['environment']['processor']}\n\n")
        f.write("## Results\n\n")
        f.write("| Benchmark | Total Operations | Mean (µs) | Median (µs) | Min (µs) | Max (µs) | Throughput (ops/sec) |\n")
        f.write("| :--- | :---: | :---: | :---: | :---: | :---: | :---: |\n")
        for r in results:
            f.write(f"| `{r['name']}` | {r['total_ops']:,} | {r['mean_us']:.2f} µs | {r['median_us']:.2f} µs | {r['min_us']:.2f} µs | {r['max_us']:.2f} µs | **{r['throughput_ops_sec']:,.0f} ops/s** |\n")
        f.write("\n> Measurements conducted using Python `timeit`/`perf_counter_ns` on bare-metal process after warm-up iterations.\n")

    print("Benchmark complete! Reports written to:")
    print(f"- {report_json_path}")
    print(f"- {report_md_path}")

if __name__ == "__main__":
    main()
