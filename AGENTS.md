@.context/TECH-STACK.md
@.context/DAISYUI.md
@.context/HTMX.md
@.context/ALPINE.md
@.context/DJANGO.md
@.context/PYTHON.md
@.context/NIX.md
@.context/PRE_COMMIT.md
@.context/DOCKER.md
@.context/SECURITY.md
@.context/AGENTS.md

---

# Agent Behavior Protocol

## 1. When in Doubt, Research
If you are stuck, unsure about a syntax, or encountering a complex error:
> **Consult Official Documentation/Styleguides immediately.**
Do not guess. Use the `browser` tool to find the authoritative source (e.g., Django docs, HTMX references, Official Styleguides) before proceeding.

## 2. Living Documentation Policy
It is **YOUR RESPONSIBILITY** to keep `AGENTS.md` and its imports alive.
-   **Missing Context?** If you find something that should be in `AGENTS.md` but isn't, **ADD IT**.
-   **Outdated Context?** If documentation drifts from code, **UPDATE IT**.
-   **New Pattern?** If you establish a new project pattern, **DOCUMENT IT**.

You are the guardian of this project's "Brain". Keep it sharp.

## 3. Workflow Commands
```bash
# Workflow
Test: python manage.py test
Test (Pytest): pytest agents/tests -q
Coverage (Pytest): pytest agents/tests --cov=agents --cov-report=term-missing
Lint: pre-commit run --all-files
Run: python manage.py runserver
Orchestration: PYTHONPATH=. dagster dev -m agents.definitions
Agents Isolated Deps: cd services/agents && python -m venv .venv && source .venv/bin/activate && pip install -e .
```

## 4. Commit Protocol
**NEVER**, under any circumstances, commit code without **EXPLICIT** user authorization.
-   Always ask for permission before running `git commit`.
-   Even if you are fixing a small error or amending a previous commit, **ASK FIRST**.
-   **NEVER SKIP CHECKS**. Always run pre-commit hooks. Do NOT use `--no-verify`.
