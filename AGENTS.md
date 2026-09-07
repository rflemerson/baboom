@.agent/context/AGENTS.md

---

# Agent Runtime Guide

## Context loading policy

- Keep root context minimal to reduce prompt bloat.
- Load additional docs from the nearest relevant `AGENTS.md` only when needed by the task.
- Priority order:
  1. `.agent/context/AGENTS.md`
  2. nearest subdirectory `AGENTS.md`
  3. task-specific docs imported from that local `AGENTS.md`

## Extended context index (load on demand)

- API backend: `apps/api/AGENTS.md`
- Infra and deploy: `infra/AGENTS.md`
- Web frontend: `apps/web/AGENTS.md`

## 1. When in Doubt, Research
If you are stuck, unsure about a syntax, or encountering a complex error:
> **Consult Official Documentation/Styleguides immediately.**
Do not guess. Use the `browser` tool to find the authoritative source (e.g., Django docs, Vue docs, Official Styleguides) before proceeding.

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
Lint: prek run --all-files
Run: python apps/api/manage.py runserver
API Deps: cd apps/api && pip install -e .
API Image: docker build -f apps/api/Dockerfile -t baboom-api .
```

## 4. Commit Protocol
**NEVER**, under any circumstances, commit code without **EXPLICIT** user authorization.
-   Always ask for permission before running `git commit`.
-   Even if you are fixing a small error or amending a previous commit, **ASK FIRST**.
-   **NEVER SKIP CHECKS**. Always run the configured git hooks/QA checks. Do NOT use `--no-verify`.
