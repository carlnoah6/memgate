# Contributing to MemGate

First off, thanks for taking the time to contribute! 🎉

The following is a set of guidelines for contributing to MemGate. These are just guidelines, not rules. Use your best judgment, and feel free to propose changes to this document in a pull request.

## 🛠️ Development Setup

1.  **Clone the repository**
    ```bash
    git clone https://github.com/your-org/memgate.git
    cd memgate
    ```

2.  **Create a virtual environment**
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    ```

3.  **Install dependencies**
    ```bash
    pip install -e .[dev]
    # If [dev] extras are not defined yet, install manually:
    pip install pytest black isort flake8
    ```

## 🧪 Running Tests

We use `pytest` for testing.

```bash
# Run all tests
pytest

# Run a specific test file
pytest memgate/tests/test_knowledge_store.py
```

Ensure all tests pass before submitting a PR.

## 🎨 Code Style

We follow PEP 8 and use `black` for formatting.

1.  **Format code**
    ```bash
    black .
    isort .
    ```

2.  **Lint code**
    ```bash
    flake8 .
    ```

## 📝 Pull Request Process

1.  Fork the repo and create your branch from `main`.
2.  If you've added code that should be tested, add tests.
3.  If you've changed APIs, update the documentation.
4.  Ensure the test suite passes.
5.  Make sure your code lints.
6.  Issue that pull request!

## 🐛 Reporting Issues

We use GitHub Issues to track public bugs. Report a bug by opening a new issue; it's that easy!

**Great Bug Reports** tend to have:

-   A quick summary and/or background.
-   Steps to reproduce.
-   What you expected would happen.
-   What actually happened.
-   Notes (possibly including why you think this might be happening, or stuff you tried that didn't work).

## 📄 License

By contributing, you agree that your contributions will be licensed under its MIT License.
