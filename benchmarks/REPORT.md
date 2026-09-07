# Benchmark Report

## Environment

- **OS**: Linux 7.0.0-29-generic
- **Architecture**: x86_64
- **Python Version**: 3.14.4
- **Processor**: x86_64

## Results

| Benchmark | Total Operations | Mean (µs) | Median (µs) | Min (µs) | Max (µs) | Throughput (ops/sec) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| `OTP Extraction (extract_otp)` | 16,000 | 6.17 µs | 5.88 µs | 1.73 µs | 137.75 µs | **155,464 ops/s** |
| `Service Detection (detect_service)` | 16,000 | 3.87 µs | 3.02 µs | 2.35 µs | 193.81 µs | **245,322 ops/s** |
| `Smart Country Lookup (get_country_details_smart)` | 14,000 | 19.23 µs | 14.77 µs | 7.37 µs | 264.43 µs | **51,373 ops/s** |
| `Cookie Parsing (parse_cookies_input)` | 1,000 | 4.65 µs | 5.48 µs | 3.07 µs | 20.78 µs | **204,220 ops/s** |

> Measurements conducted using Python `timeit`/`perf_counter_ns` on bare-metal process after warm-up iterations.
