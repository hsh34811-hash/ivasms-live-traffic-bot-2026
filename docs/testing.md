# Testing Guide

RAVEN BOT X maintains a suite of unit tests verifying core parsers, data lookups, and multi-language integrity.

---

## Running the Test Suite

Execute all unit tests using Python's built-in test runner:

```bash
python3 -m unittest discover -s tests -p "test_*.py" -v
```

Or run via `pytest` if installed:

```bash
pytest tests/ -v
```

---

## Test Suite Structure

| Test Module | Coverage Area |
| :--- | :--- |
| `tests/test_otp_parser.py` | Verification code extraction regex, edge cases, service detection. |
| `tests/test_country_data.py` | Dial code matching, country name fuzzy lookup, fallback handling. |
| `tests/test_locales.py` | Cross-language dictionary key completeness, string template interpolation. |
| `tests/test_cookie_parser.py` | Netscape format parsing, JSON format parsing, empty input validation. |

---

## Writing New Tests

When contributing new features or bug fixes, add corresponding test cases under `tests/`:

```python
import unittest
from main import extract_otp

class TestNewPattern(unittest.TestCase):
    def test_custom_service_code(self):
        msg = "Custom Service: Your code is 123456"
        self.assertEqual(extract_otp(msg), "123456")
```\n