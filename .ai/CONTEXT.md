# 🧠 Baboom Project Context (AI Integration)

**Project Purpose:** Baboom is a **supplement cost-benefit comparator**. It analyzes supplement prices (protein, etc) and calculates the real value (price per gram of protein) to help users find the best deal. It redirects users via affiliate links to store pages.

---

## 📌 Critical Rules of Engagement
1.  **Workflow**: Use `pre-commit run --all-files` for Quality Assurance.
2.  **Versions**: **Python 3.14+** and **Django 6.0**.
3.  **Filesystem**: Modify only files within the active workspace.
4.  **Commits**: **DO NOT COMMIT**. Stage your changes (`git add .`) and propose the Angular-style message in your final notification. User will execute the commit.
5.  **Knowledge Sharing**: If you discover a new pattern, fix, or requirement, **UPDATE THIS FILE**. Keep the context living and evolving.
6.  **Context**: Read this file fully before starting tasks.

---

## 🛠️ Technology Stack (TALL-Django)

| Layer | Technology | Details |
|-------|------------|---------|
| **Backend** | Django 6.0 | "Fat Models", Async ORM, Native Background Tasks. |
| **Frontend** | Tailwind CSS | Utility-first via `django-tailwind-cli`. |
| **Interactivity** | Alpine.js | Client-side reactive state (v3.15). |
| **Server Events** | HTMX | HTML-over-the-wire updates. |
| **Icons** | Heroicons | `heroicons[django]` wrapper. |

---

## 🦄 Backend Best Practices (Django 6.0)

### 1. New Features Usage
*   **Background Tasks**: Use the native `@task` decorator for async jobs (e.g. price scraping).
    ```python
    from django.tasks import task
    @task
    def update_prices(): ...
    ```
*   **Partials**: Use `{% partialdef %}` for HTMX fragments.
*   **CSP**: Configure `CSP_SOURCES` natively in settings.

### 2. Architecture
*   **Project Structure**: Monorepo root. Apps in `core`, `products`.
*   **Settings**: Split by environment (`base.py`, etc).
*   **Business Logic**: Keep views skinny. Put logic in Models or Service layers (e.g., `ProductQuerySet.with_stats` for calculations).

---

## 🎨 Frontend Best Practices

### Tailwind CSS
*   **Mobile-First**: `w-full md:w-64`.
*   **No `@apply`**: Use Django `{% include %}` for components instead of abstraction capabilities of CSS.
*   **Watcher**: Run `python manage.py tailwind watch`.

### HTMX & Alpine.js
*   **CSRF**: Configured globally in `base.html` (`hx-headers`).
*   **Partials**: Return only the HTML fragment needed for the request.
*   **State**: Use Alpine (`x-data`) for purely client-side UI (modals, dropdowns). Bridge to server events via `hx-trigger`.

### Heroicons
*   **Usage**: `{% heroicon_outline "shopping-cart" class="h-5 w-5" %}`.
*   **Rules**: Always specify `class="h-X w-X"`.

---

## ⚙️ Development Workflow

### Running Locally
```bash
source .venv/bin/activate
# OPTION A: Quick Start (Reset DB + Seed + Test)
./.ai/automation/setup_local.sh

# OPTION B: Manual Run
python manage.py runserver
```

### Quality Assurance (Mandatory)
Before "delivering" a task, you must ensure the suite passes:
```bash
./.ai/automation/verify_work.sh
```
This runs `python manage.py test` AND `pre-commit run --all-files`. If it fails, fix the issues.

---

## 📂 Directories
*   `.ai/`: **AI Workspace** (Scripts, Context, Seed).
*   `.ai/temp/`: **Sandbox**. Create any ad-hoc script here.
*   `baboom/`: Main project configuration.
*   `core/`, `products/`: Application logic.
