#!/usr/bin/env bash
set -e

echo "=== Running Python compilation check ==="
python3 -m py_compile main.py country_data.py locales.py ivasms_manager.py

echo "=== Running unit test suite ==="
python3 -m unittest discover -s tests -p "test_*.py" -v

echo "=== Running environment check ==="
python3 scripts/verify_environment.py

echo "=== All test stages passed successfully! ==="
