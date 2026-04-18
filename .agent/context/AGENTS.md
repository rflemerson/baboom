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
Lint: prek run --all-files
Lint (Just): just check
Lint API (Just): just api-lint
Lint Agents (Just): just agents-lint
Run: python apps/api/manage.py runserver
Orchestration (Agents): PYTHONPATH=services/agents:. dagster dev -m agents.definitions
API Isolated Deps: cd apps/api && pip install -e .
Agents Isolated Deps: cd services/agents && python -m venv .venv && source .venv/bin/activate && pip install -e .
API Image: docker build -f apps/api/Dockerfile -t baboom-api .
Agents Image: docker build -f services/agents/Dockerfile -t baboom-agents .
```

### IV. Coding Standards (The "Rules")
Use "Do" and "Don't" format.
- **Do**: Use explicit typing, small functions, and architecture-aligned boundaries.
- **Don't**: Silence linters or reintroduce legacy frontend patterns.

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

## 6.1 Refactor Integrity Policy
- Fix code to satisfy the active lint/type/test stack. Do not make progress by suppressing the tool.
- Avoid local escapes such as `noqa`, `type: ignore`, `stylelint-disable`, broad `ignore` globs, or turning rules off unless the code is generated or a framework boundary truly requires it.
- Prefer stronger types, smaller functions, `TYPE_CHECKING` imports, `ClassVar`, immutable metadata, and clearer names over rule suppression.
- If the current docs still mention legacy patterns that are no longer the project direction, update the docs before continuing.
- Do not be afraid to delete legacy files, remove stale abstractions, or rename old view-shaped APIs when the current architecture no longer uses them.
- Prefer removing dead paths over documenting them forever.

## 6.2 Frontend Direction Policy
- Do not use legacy Django template UI patterns for new public frontend work.
- The public frontend lives in `apps/web` and should follow the Vue-specific docs in `apps/web/AGENTS.md` and `apps/web/.agents/`.

## 7. Agents Pipeline Contract (Dagster)
- The Django scrapers are API-first. They persist product context in `ScrapedPage.api_context` and HTML-derived structured data in `ScrapedPage.html_structured_data`.
- Dagster must consume `sourcePageApiContext` as its primary deterministic input. `sourcePageHtmlStructuredData` is auxiliary context for future enrichment and should not replace `api_context` by default.
- The agents pipeline no longer owns local HTML scraping, image manifest generation, CV scoring, or storage-side candidate materialization.
- The deterministic handoff is:
  - `downloaded_assets` -> normalize the `ScrapedItem` + `ScrapedPage` payload from the API
  - `prepared_extraction_inputs` -> extract ordered image URLs and JSON context from `api_context`
- The non-deterministic handoff is:
  - `raw_extraction` -> send `api_context` JSON plus raw image URLs to the multimodal model
  - `product_analysis` -> convert raw text into one recursive `ExtractedProduct` tree
- `extraction_handoff` is a final handoff asset only: it emits source identifiers, raw extraction text, and the extracted product tree. It must not create catalog products, variants, or components.
- Combo/kit structure is represented by `ExtractedProduct.children`; there is no `items` list, `components` list, or `is_combo` flag in the agents output.
