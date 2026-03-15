@.agent/context/TECH-STACK.md
@.agent/context/PRE_COMMIT.md
@.agent/context/SECURITY.md
@.agent/context/AGENTS.md

---

# Agent Runtime Guide

## Context loading policy

- Keep root context minimal to reduce prompt bloat.
- Load additional docs from `.agent/context/` only when needed by the task.
- Priority order:
  1. `.agent/context/AGENTS.md`
  2. task-specific docs (framework/tool/security)

## Extended context index (load on demand)

- UI: `.agent/context/DAISYUI.md`, `.agent/context/HTMX.md`, `.agent/context/ALPINE.md`
- Backend: `.agent/context/DJANGO.md`, `.agent/context/PYTHON.md`
- Infra: `.agent/context/NIX.md`, `.agent/context/DOCKER.md`

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
Test: python apps/api/manage.py test
Test (Pytest): PYTHONPATH=services/agents:. pytest services/agents/agents/tests -q
Coverage (Pytest): PYTHONPATH=services/agents:. pytest services/agents/agents/tests --cov=agents --cov-report=term-missing
Lint: prek run --all-files
Lint (Just): just check
Lint API (Just): just api-lint
Lint Agents (Just): just agents-lint
Run: python apps/api/manage.py runserver
Orchestration: PYTHONPATH=services/agents:. dagster dev -m agents.definitions
API Deps: cd apps/api && pip install -e .
Agents Isolated Deps: cd services/agents && python -m venv .venv && source .venv/bin/activate && pip install -e .
API Image: docker build -f apps/api/Dockerfile -t baboom-api .
Agents Image: docker build -f services/agents/Dockerfile -t baboom-agents .
```

## 4. Commit Protocol
**NEVER**, under any circumstances, commit code without **EXPLICIT** user authorization.
-   Always ask for permission before running `git commit`.
-   Even if you are fixing a small error or amending a previous commit, **ASK FIRST**.
-   **NEVER SKIP CHECKS**. Always run the configured git hooks/QA checks. Do NOT use `--no-verify`.
