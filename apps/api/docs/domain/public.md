# Public Use Cases

This document groups the public-facing use cases exposed to external users.

## Actor: Public Visitor

### Description

- External user consuming public catalog and alert subscription flows.

### Main goals

- browse the public catalog
- subscribe to price alerts

### Main entry points

- GraphQL public catalog query
- GraphQL alert subscription mutation

## Scope

- alert subscription
- public catalog browsing

## UC-01 Subscribe To Alerts

### Goal

Subscribe an email address to price alerts.

### Primary actor

- Public Visitor

### Supporting actors

- GraphQL boundary
- AlertSubscriptionService

### Trigger

- The actor submits an email address to the alert subscription mutation.

### Preconditions

- An email address is provided.

### Postconditions

- A new alert subscription exists, or the system reports that the email is already subscribed.

### Main success flow

1. The actor submits an email address.
2. The system normalizes the email.
3. The system checks whether the email is already subscribed.
4. If it is not subscribed, the system validates the email structure.
5. The system creates the alert subscriber.
6. The system returns a successful subscription result.

### Alternate flows

#### A1. Already subscribed

1. The system finds an existing subscriber with the normalized email.
2. The system returns `already_subscribed = true`.

#### A2. Invalid email

1. The system validates the email.
2. Validation fails.
3. The system returns validation errors.

### Business rules

- Emails are normalized before validation and lookup.
- Duplicate subscriptions are prevented by the service workflow.

## UC-02 Query Public Catalog

### Goal

Return a filtered, sorted, paginated public catalog listing.

### Primary actor

- Public Visitor

### Supporting actors

- GraphQL boundary
- Catalog query layer in `selectors.py`

### Trigger

- The actor requests catalog products through GraphQL.

### Preconditions

- The GraphQL request is authenticated according to the API rules.

### Postconditions

- The actor receives a paginated catalog result with public products and derived metrics.

### Main success flow

1. The actor submits catalog filters and paging parameters.
2. The GraphQL boundary normalizes the incoming arguments.
3. The catalog query layer builds the annotated base queryset.
4. The query layer applies public visibility rules.
5. The query layer applies search, brand filtering, numeric filters, and sorting.
6. The query layer returns a stable ordered queryset.
7. GraphQL slices the result into the requested page and returns page metadata.

### Alternate flows

#### A1. No filters provided

1. The system returns the default public catalog ordering.

#### A2. Equal metric values

1. Multiple products tie on the primary sort metric.
2. The system applies stable fallback ordering.

### Business rules

- Catalog query composition lives in `selectors.py`, not in GraphQL and not in services.
- Latest price selection uses a stable tie-breaker.
- Public catalog sorting is deterministic.
