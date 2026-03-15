# AGENTS.md Best Practices

This document serves as a "Meta-Guide" for creating `AGENTS.md` files, based on the [Agents.md Standard](https://agents.md/).

## 1. Philosophy: "README for Agents"
While `README.md` is for humans, `AGENTS.md` is for Large Language Models (LLMs). It should be:
- **Predictable**: Always at the root (`/AGENTS.md`).
- **High-Signal**: Dense, actionable information. No fluff.
- **Context-First**: Optimized for RAG (Retrieval-Augmented Generation) ingestion.

## 2. File Naming & Location
- **Root**: `/AGENTS.md` (Main entry point).
- **Subdirectories**: `/subdir/AGENTS.md` (Context specific to that folder).
- **Imports**: Use `@` syntax to import modular context files (e.g., `@.context/tech-stack.md`).

## 3. Recommended Structure
A robust `AGENTS.md` should follow this structure:

### I. Project Context
Brief, high-level overview. define the "Identity" of the project.
> "Baboom is a supplement cost-benefit comparator..."

### II. Tech Stack & Dependencies
List versions explicitly. Agents assume defaults if not specified.
> "Python 3.14.2, Django 6.0, Tailwind CSS (Standalone)"

### III. Development Workflow
Explicit commands for common tasks. Don't let the agent guess.
```bash
# Workflow
Test: python apps/api/manage.py test
Test (Pytest): PYTHONPATH=services/agents:. pytest services/agents/agents/tests -q
Coverage (Pytest): PYTHONPATH=services/agents:. pytest services/agents/agents/tests --cov=agents --cov-report=term-missing
Lint: pre-commit run --all-files
Run: python apps/api/manage.py runserver
Orchestration (Agents): PYTHONPATH=services/agents:. dagster dev -m agents.definitions
API Isolated Deps: cd apps/api && pip install -e .
Agents Isolated Deps: cd services/agents && python -m venv .venv && source .venv/bin/activate && pip install -e .
API Image: docker build -f apps/api/Dockerfile -t baboom-api .
Agents Image: docker build -f services/agents/Dockerfile -t baboom-agents .
```

### IV. Coding Standards (The "Rules")
Use "Do" and "Don't" format.
- **Do**: Use functional views for HTMX.
- **Don't**: Use inline styles.

## 4. Anti-Patterns to Avoid
- **Duplication**: Don't copy-paste large docs. Import them.
- **Vagueness**: Avoid "Write good code". Be specific: "Use Python Type Hints".
- **Outdated Info**: An outdated `AGENTS.md` is worse than none. Keep it live.

## 5. Metadata for Tools (Optional)
You can embed hints for specific AI tools if needed (e.g., strict non-searchable exclusions).

## 6. Maintenance Policy: Living Documentation
**CRITICAL RULE**: Documentation must never get stale.
1.  **Update on Sight**: If you read this or any documentation (e.g., in `.context/`) and find it conflicts with the actual code/environment, **you must update it immediately** before proceeding with other tasks.
2.  **Update on Change**: If you make *any* significant change to the code (e.g., adding a library, changing a workflow, refactoring architecture), you **must search for and update** the relevant documentation in the same step.

## 7. Agents Pipeline Contract (Dagster)
- Scraper stage must stay lightweight and store artifacts only:
  - `source.html`, `image_manifest.json`, `site_data.json`, optional `catalog_context.json`.
- Heavy image download/CV scoring must run in Dagster (`ocr_extraction`) and persist:
  - `images/*` + `candidates.json`.
- `ocr_extraction` must always send context blocks (`[SITE_DATA]`, `[CATALOG_CONTEXT]`) and expose fallback metadata when running text-only mode.
- `product_analysis` must enforce schema consistency plus catalog consistency (allowed flavors/variants when context exists).
