# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [2.0.0] - 2026-09-07

### Added
- Standardized file structure with entrypoint [`main.py`](main.py).
- Multilingual support for 7 languages (Arabic, English, Urdu, Russian, Turkish, Persian, Hindi) in [`locales.py`](locales.py).
- Automated hourly group reminder worker with 60-second self-destruct mechanism.
- Comprehensive test suite in [`tests/`](tests/) covering OTP extraction, country lookup, cookie normalization, and localization.
- Performance benchmark harness in [`benchmarks/`](benchmarks/) with verified execution reports.
- Full modular documentation architecture in [`docs/`](docs/).
- Contributor and community health files (`CODE_OF_CONDUCT.md`, `SUPPORT.md`, `THIRD_PARTY_NOTICES.md`).
- Automated Continuous Integration (CI) workflow for Python 3.10, 3.11, and 3.12 in [`.github/workflows/ci.yml`](.github/workflows/ci.yml).

### Changed
- Transitioned project license to **PolyForm Noncommercial License 1.0.0** (Source-Available / Noncommercial).
- Refactored Telegram inline buttons to use native Telegram styling (`primary`, `success`, `danger`) with zero emoji clutter.
- Removed all legacy decorative borders and box drawing characters for clean visual ergonomics.
- Environment variables support for sensitive configuration (`.env.example`).

### Fixed
- Typo in animated header badge SVG.
- Cookie parser handling for single-item and multi-line Netscape HTTP cookie formats.
- Error handling on Cloudflare 403 challenge detection.
