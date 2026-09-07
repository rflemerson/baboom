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
Lint: prek run --all-files
Run: python apps/api/manage.py runserver
API Isolated Deps: cd apps/api && pip install -e .
API Image: docker build -f apps/api/Dockerfile -t baboom-api .
```

### IV. Coding Standards (The "Rules")
Use "Do" and "Don't" format.
- **Do**: Use explicit typing, small functions, and architecture-aligned boundaries.
- **Don't**: Silence linters or add public frontend flows to Django templates.

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
- Update documentation alongside changes in project direction.
- Remove unused files and abstractions when the current architecture no longer uses them.
- Prefer removing dead paths over documenting them forever.

## 6.2 Frontend Direction Policy
- Public frontend work belongs in Vue, not Django templates.
- The public frontend lives in `apps/web` and should follow the Vue-specific docs in `apps/web/AGENTS.md` and `apps/web/.agents/`.

## 7. Local Product Review Contract
- Product review is interactive and runs on an operator workstation; the Baboom
  server does not host chat or model orchestration.
- Django owns the authenticated GraphQL contract for queue discovery, targeted
  checkout, resume, heartbeat, release, extraction staging, duplicate search,
  and explicit approval.
- Scraped context remains API-first in `ScrapedPage.api_context` and
  `ScrapedPage.html_structured_data`; review clients also receive normalized
  `imageUrls`.
- Staging a draft moves an item to `review` without touching the catalog.
- Only explicit approval may link an offer or create an unpublished product.
- Publication and detailed nutrition/component curation remain in Django admin.
