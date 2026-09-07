# Development Guide

This guide is intended for developers contributing to the RAVEN BOT X codebase.

---

## Development Setup

1. Fork and clone the repository.
2. Create and activate a virtual environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```
3. Install development dependencies:
   ```bash
   pip install -r requirements.txt -r requirements-dev.txt
   ```

---

## Code Quality & Standards

- **PEP 8 Compliance**: Code must adhere to standard Python style guidelines.
- **Maximum Line Length**: 160 characters for complex regex and multi-language dictionary definitions.
- **Typing & Compilation**: All modified files must compile cleanly:
   ```bash
   python3 -m py_compile main.py country_data.py locales.py ivasms_manager.py
   ```
- **Linting**:
   ```bash
   flake8 --max-line-length=160 --ignore=E501,W503 main.py country_data.py locales.py
   ```

---

## Adding a New Language

To add support for a new language:

1. Open `locales.py`.
2. Add the language metadata to `SUPPORTED_LANGUAGES`:
   ```python
   SUPPORTED_LANGUAGES["es"] = {"name": "Español", "flag": "🇪🇸"}
   ```
3. Add a complete translation dictionary under `TRANSLATIONS["es"]` containing all required keys.
4. Run `python3 -m unittest tests/test_locales.py` to ensure key parity.\n