# Contributing to RAVEN BOT X

Thank you for your interest in contributing to **RAVEN BOT X**.
We welcome contributions, bug fixes, and suggestions that align with our noncommercial mission and architectural standards.

---

## Legal & Licensing Note

By contributing to this repository, you agree that all submitted contributions will be licensed under the **PolyForm Noncommercial License 1.0.0**. Commercial use and resale of contributions or modified builds are strictly prohibited.

---

## How to Contribute

### 1. Reporting Bugs
- Search existing [GitHub Issues](https://github.com/Raven-Team/raven-bot-x/issues) to avoid duplicate reports.
- If you find a new bug, submit an issue using the [Bug Report Template](.github/ISSUE_TEMPLATE/bug_report.md).
- Include terminal logs, steps to reproduce, and environment details.

### 2. Suggesting Enhancements
- Submit enhancement suggestions using the [Feature Request Template](.github/ISSUE_TEMPLATE/feature_request.md).
- Clearly explain the use case and technical rationale.

### 3. Pull Request Process
1. Fork the repository and create your branch from `main`:
   ```bash
   git checkout -b feature/your-feature-name
   ```
2. Set up your development environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt -r requirements-dev.txt
   ```
3. Ensure all tests pass:
   ```bash
   bash scripts/run_tests.sh
   ```
4. Keep pull requests focused on a single change or fix.
5. Submit the pull request using our [Pull Request Template](.github/PULL_REQUEST_TEMPLATE.md).
