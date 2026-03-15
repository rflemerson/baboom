# Frontend Migration Contract

## Goal

Migrate the public Baboom experience from Django templates/HTMX to `apps/web` (Vue),
while keeping Django admin inside `apps/api`.

This document defines:

- what the current Django frontend does
- what data the Vue frontend needs
- which GraphQL operations are still missing
- when a Vue screen is ready to replace the Django version

## Current Public Scope

The current public frontend served by Django is limited to two user-facing flows:

1. Product catalog at `/`
2. Alert subscription flow at `/subscribe/`

Relevant implementation:

- routes: [core/urls.py](/home/rafael/Documents/baboom/apps/api/core/urls.py)
- views: [core/views.py](/home/rafael/Documents/baboom/apps/api/core/views.py)
- templates: [base.html](/home/rafael/Documents/baboom/apps/api/core/templates/base.html)
- header partial: [header.html](/home/rafael/Documents/baboom/apps/api/core/templates/core/partials/header.html)
- list selector: [selectors.py](/home/rafael/Documents/baboom/apps/api/core/selectors.py)
- filters: [filters.py](/home/rafael/Documents/baboom/apps/api/core/filters.py)
- alert form: [forms.py](/home/rafael/Documents/baboom/apps/api/core/forms.py)

## Screen Inventory

### 1. Catalog Page

Route:

- `/`

Current Django behavior:

- renders full page on normal request
- renders partial results on HTMX request
- supports list view and grid view
- supports client-side remembered view mode through `localStorage`
- supports filtering, sorting, pagination, and per-page size changes

Current UI pieces:

- page shell and header
- toolbar
- filters button and drawer
- product results
- list card
- grid card
- price tag
- pagination

Relevant component files:

- [toolbar.html](/home/rafael/Documents/baboom/apps/api/core/components/list/toolbar/toolbar.html)
- [filters.html](/home/rafael/Documents/baboom/apps/api/core/components/list/filters/filters.html)
- [results.html](/home/rafael/Documents/baboom/apps/api/core/components/list/results/results.html)
- [card_list.html](/home/rafael/Documents/baboom/apps/api/core/components/list/card_list/card_list.html)
- [card_grid.html](/home/rafael/Documents/baboom/apps/api/core/components/list/card_grid/card_grid.html)
- [pagination.html](/home/rafael/Documents/baboom/apps/api/core/components/list/pagination/pagination.html)

### 2. Alert Subscription

Route:

- `/subscribe/`

Current Django behavior:

- GET + HTMX returns subscription form
- POST validates email
- returns success partial when created
- returns duplicate partial if email already exists
- returns form with inline error on invalid email
- non-HTMX requests redirect to catalog and use Django messages

Relevant files:

- [views.py](/home/rafael/Documents/baboom/apps/api/core/views.py)
- [forms.py](/home/rafael/Documents/baboom/apps/api/core/forms.py)
- [form.html](/home/rafael/Documents/baboom/apps/api/core/templates/core/partials/alerts/form.html)
- [success.html](/home/rafael/Documents/baboom/apps/api/core/templates/core/partials/alerts/success.html)
- [duplicate.html](/home/rafael/Documents/baboom/apps/api/core/templates/core/partials/alerts/duplicate.html)

## Catalog Requirements

### Data Needed Per Product Card

The Vue catalog needs enough fields to support both current card variants.

Minimum data currently rendered:

- `id`
- `name`
- `brand.name`
- `category.name`
- `tags[].name`
- `weight`
- `packaging` or display label
- `concentration`
- `total_protein`
- `last_price`
- `price_per_gram`
- `external_link`

### Filter Inputs Needed

Current Django filters expose:

- `search`
- `brand`
- `price_min`
- `price_max`
- `price_per_gram_min`
- `price_per_gram_max`
- `concentration_min`
- `concentration_max`
- `sort_by`
- `sort_dir`
- `per_page`
- `page`

See: [filters.py](/home/rafael/Documents/baboom/apps/api/core/filters.py)

### Sorting Needed

Current allowed sort keys:

- `price_per_gram`
- `last_price`
- `total_protein`
- `concentration`

Sort direction:

- `asc`
- `desc`

### Pagination Needed

Current supported page sizes:

- `12`
- `24`
- `48`

Current page metadata displayed:

- current item range
- total item count
- previous / next buttons
- local page number window

## Alert Subscription Requirements

The Vue frontend needs one mutation replacing the current HTMX form flow.

Input:

- `email`

Output should distinguish:

- success
- duplicate subscription
- invalid input
- unexpected server error

## Existing GraphQL Coverage

Current public-ish queries are not enough to replace the catalog page.

Already present:

- `hello`
- `products(limit, offset)`
- `product(productId)`
- `categories`
- `tags`

See: [core/graphql/queries.py](/home/rafael/Documents/baboom/apps/api/core/graphql/queries.py)

Why this is not enough:

- `products(limit, offset)` does not use the annotated catalog selector
- it does not expose the current filter behavior
- it does not expose page metadata
- it does not reflect the current public sort model

## GraphQL Operations Required

### 1. Catalog Query

Recommended name:

- `catalogProducts`

Recommended arguments:

- `search`
- `brand`
- `priceMin`
- `priceMax`
- `pricePerGramMin`
- `pricePerGramMax`
- `concentrationMin`
- `concentrationMax`
- `sortBy`
- `sortDir`
- `page`
- `perPage`

Recommended response shape:

- `items`
- `pageInfo`
- `totalCount`
- `perPage`
- `currentPage`

Per item:

- fields listed in "Data Needed Per Product Card"

### 2. Alert Subscription Mutation

Recommended name:

- `subscribeAlerts`

Recommended input:

- `email`

Recommended response shape:

- `success`
- `code`
- `message`

Suggested `code` values:

- `created`
- `duplicate`
- `invalid_email`
- `server_error`

## Migration Phases

### Phase 1: API Contract

Build missing GraphQL operations before the Vue UI depends on ad hoc workarounds.

Deliverables:

- `catalogProducts` query
- `subscribeAlerts` mutation

### Phase 2: Vue Catalog Shell

Build the catalog page in Vue with:

- query execution
- empty state
- loading state
- error state

No visual parity requirement yet.

### Phase 3: Vue Feature Parity

Add:

- filters
- sorting
- pagination
- list/grid mode
- alert subscribe flow

### Phase 4: Visual Parity

Match the current public experience closely enough to switch traffic.

### Phase 5: Django Public Cleanup

After Vue is stable:

- remove public template rendering for the catalog
- remove HTMX-specific partial flow for alerts
- keep Django admin untouched

## Definition of Done

The Vue catalog is ready to replace Django when:

- it renders the same product inventory
- filters match current Django behavior
- sorting matches current Django behavior
- pagination matches current Django behavior
- list/grid view is available
- alert subscription works for success, duplicate, and invalid input
- loading, empty, and error states exist
- GraphQL fully supports the page without frontend-side business-rule duplication

## Non-Goals

- migrating Django admin
- rewriting agents integration
- replacing GraphQL with REST
- deleting Django public pages before Vue reaches parity
