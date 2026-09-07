# Benchmarking Guide

RAVEN BOT X includes a dedicated, reproducible benchmarking harness to profile latency, memory, and throughput of critical path operations.

---

## Running Benchmarks

Execute the benchmark script directly:

```bash
python3 benchmarks/benchmark_parser.py
```

The script will:
1. Warm up Python JIT/bytecode caches.
2. Run thousands of iterations measuring execution duration with high-resolution timers (`time.perf_counter_ns`).
3. Output a detailed JSON report (`benchmarks/benchmark_results.json`).
4. Generate an updated Markdown table in [`benchmarks/REPORT.md`](../benchmarks/REPORT.md).

---

## Benchmarked Components

1. **OTP Extraction (`extract_otp`)**: Evaluates multi-pattern regex matching against multilingual SMS text.
2. **Service Detection (`detect_service`)**: Profiles dictionary matching and keyword normalization.
3. **Smart Country Lookup (`get_country_details_smart`)**: Measures dial code prefix resolution and range name parsing.
4. **Cookie Parsing (`parse_cookies_input`)**: Measures deserialization of Netscape HTTP cookie files and JSON arrays.\n