# Admin Use Cases

This document groups the use cases handled by the Catalog Administrator through Django admin.

## Actor: Catalog Administrator

### Description

- Human operator using Django admin as the official domain interface.

### Main goals

- create support entities such as brands, stores, flavors, tags, and categories
- create products
- update product metadata
- manage nutrition
- manage store listings
- manage API keys when needed
- use technical support admin surfaces when operationally necessary

### Main entry point

- `ProductAdmin`

## Scope

- support data maintenance
- product creation and editing
- nutrition management
- store listing management

## UC-01 Manage Brands

### Goal

Maintain brand records used by products in the catalog.

### Primary actor

- Catalog Administrator using Django admin

### Supporting actors

- Django admin

### Trigger

- The actor creates, edits, or reviews a brand in the admin.

### Preconditions

- The actor has access to the Django admin.

### Postconditions

- The catalog brand records reflect the submitted admin changes.

### Main success flow

1. The actor provides the brand name and optional supporting fields.
2. The system validates the submitted data.
3. The system persists the brand changes.
4. The system makes the resulting brand data available for product workflows.

### Alternate flows

#### A1. Invalid submitted data

1. The system detects invalid form data.
2. The system rejects the submission with validation errors.

### Business rules

- Brand is a support entity used by product workflows.

## UC-02 Manage Stores

### Goal

Maintain store records that can be linked to products.

### Primary actor

- Catalog Administrator using Django admin

### Supporting actors

- Django admin

### Trigger

- The actor creates, edits, or reviews a store in the admin.

### Preconditions

- The actor has access to the Django admin.

### Postconditions

- The catalog store records reflect the submitted admin changes.

### Main success flow

1. The actor provides the store data.
2. The system validates the submitted data.
3. The system persists the store changes.
4. The resulting store data becomes available for product store listings.

### Alternate flows

#### A1. Invalid submitted data

1. The system detects invalid form data.
2. The system rejects the submission with validation errors.

### Business rules

- Store is a support entity used by product store listing workflows.

## UC-03 Manage Flavors

### Goal

Maintain flavor records that can be linked to nutrition profiles.

### Primary actor

- Catalog Administrator using Django admin

### Supporting actors

- Django admin

### Trigger

- The actor creates, edits, or reviews a flavor in the admin.

### Preconditions

- The actor has access to the Django admin.

### Postconditions

- The flavor support records reflect the submitted admin changes.

### Main success flow

1. The actor provides the flavor data.
2. The system validates the submitted data.
3. The system persists the flavor changes.

### Alternate flows

#### A1. Invalid submitted data

1. The system detects invalid form data.
2. The system rejects the submission with validation errors.

### Business rules

- Flavor is a support entity used by nutrition profile workflows.

## UC-04 Manage Tags

### Goal

Maintain tags that classify products.

### Primary actor

- Catalog Administrator using Django admin

### Supporting actors

- Django admin
- Tree-based tag model

### Trigger

- The actor creates, edits, or reviews a tag in the admin.

### Preconditions

- The actor has access to the Django admin.

### Postconditions

- The tag classification tree reflects the submitted admin changes.

### Main success flow

1. The actor provides the tag data.
2. The system validates the submitted data.
3. The system persists the tag changes in the tag tree.

### Alternate flows

#### A1. Invalid submitted data

1. The system detects invalid form data.
2. The system rejects the submission with validation errors.

### Business rules

- Tags may be hierarchical.
- Tags are support entities used by product metadata workflows.

## UC-05 Manage Categories

### Goal

Maintain categories that classify products in the catalog tree.

### Primary actor

- Catalog Administrator using Django admin

### Supporting actors

- Django admin
- Tree-based category model

### Trigger

- The actor creates, edits, or reviews a category in the admin.

### Preconditions

- The actor has access to the Django admin.

### Postconditions

- The category tree reflects the submitted admin changes.

### Main success flow

1. The actor provides the category data.
2. The system validates the submitted data.
3. The system persists the category changes in the category tree.

### Alternate flows

#### A1. Invalid submitted data

1. The system detects invalid form data.
2. The system rejects the submission with validation errors.

### Business rules

- Categories may be hierarchical.
- Categories are support entities used by product metadata and catalog workflows.

## UC-06 Manage API Keys

### Goal

Maintain API keys used for authenticated API access.

### Primary actor

- Catalog Administrator using Django admin

### Supporting actors

- Django admin
- APIKey model

### Trigger

- The actor creates, edits, or reviews an API key entry in the admin.

### Preconditions

- The actor has access to the Django admin.

### Postconditions

- The API key records reflect the submitted admin changes.

### Main success flow

1. The actor provides the API key metadata.
2. The system validates the submitted data.
3. The system persists the API key changes.
4. The model generates the concrete key value when a new key is created without one.

### Alternate flows

#### A1. Invalid submitted data

1. The system detects invalid form data.
2. The system rejects the submission with validation errors.

### Business rules

- The secret key value is generated by the model when absent.
- API keys are technical support entities, not catalog content.

## UC-07 Manage Product From Admin

### Goal

Create or update a product through Django admin.

### Primary actor

- Catalog Administrator

### Supporting actors

- ProductAdmin
- ProductCreateService
- ProductMetadataUpdateService
- ProductNutritionService
- ProductStoreService

### Trigger

- The actor creates a new product or edits an existing product in `ProductAdmin`.

### Preconditions

- For creation:
  - brand is selected
  - product name is provided
  - weight is provided
  - packaging is provided
- For update:
  - the target product exists

### Postconditions

- The product exists with the submitted admin state.
- Optional nutrition and store listing workflows are applied through the official admin flow.

### Main success flow

1. The actor opens `ProductAdmin`.
2. The actor enters new product data or edits an existing product.
3. The system validates the admin form.
4. If the product is new, the admin maps the form data to `ProductCreateInput`.
5. The system creates the product through `ProductCreateService`.
6. If the product already exists, the admin maps the form data to `ProductMetadataUpdateInput`.
7. The system updates the product through `ProductMetadataUpdateService`.
8. If nutrition input is present, the admin applies the nutrition workflow.
9. If store listings are present, the admin applies the store listing workflow.
10. The system returns to the saved product.

### Alternate flows

#### A1. Duplicate EAN on creation

1. The system detects an existing product with the same EAN.
2. The system rejects creation with a validation error.

#### A2. Target product not found on update

1. The system cannot load the target product.
2. The system returns a validation error.

#### A3. No nutrition selected

1. The actor does not provide nutrition.
2. The system skips nutrition attachment.

#### A4. No store listings submitted

1. The actor does not provide store listings.
2. The system skips store synchronization.

### Business rules

- Admin product creation must go through `ProductCreateService`.
- Admin product updates must go through `ProductMetadataUpdateService`.
- Nutrition and store listing flows must not bypass their services.
- Brand, weight, and EAN are not part of the current official edit workflow.

## UC-08 Manage Product Nutrition From Admin

### Goal

Manage product nutrition through the official Django admin workflow.

### Primary actor

- Catalog Administrator

### Supporting actors

- ProductAdmin
- ProductAdminForm
- ProductNutritionService

### Trigger

- The actor chooses a nutrition mode in `ProductAdmin`.

### Preconditions

- The target product exists.

### Postconditions

- The product has the desired nutrition profile state.

### Main success flow

1. The actor chooses a nutrition mode in `ProductAdmin`.
2. The system validates the nutrition-specific form fields.
3. If the actor selects an existing table, the system links it to the product.
4. If the actor enters a new table, the admin maps the form to a nutrition payload.
5. The system creates new nutrition facts from the submitted values.
6. The system attaches the resulting nutrition profile to the product.

### Alternate flows

#### A1. No nutrition profile

1. The actor selects the mode without nutrition.
2. The system clears current nutrition profiles.

#### A2. Existing table required but not selected

1. The actor selects the existing-table mode.
2. The form detects that no table was selected.
3. The system rejects the submission with validation errors.

#### A3. New nutrition is incomplete

1. The actor selects the new-table mode.
2. Required nutrition fields are missing.
3. The system rejects the submission with validation errors.

### Business rules

- New nutrition submissions are stored as distinct facts tables.
- Reuse is explicit: the actor must select an existing nutrition table.
- Admin nutrition management must go through `ProductNutritionService`.

## UC-09 Manage Product Store Listings From Admin

### Goal

Manage product store listings through the official Django admin workflow.

### Primary actor

- Catalog Administrator

### Supporting actors

- ProductAdmin
- ProductStoreInlineFormSet
- ProductStoreService

### Trigger

- The actor edits the store listing inline in `ProductAdmin`.

### Preconditions

- The target product exists.

### Postconditions

- The product store listings match the desired admin state.

### Main success flow

1. The actor edits the store listing inline rows in `ProductAdmin`.
2. The admin formset validates the inline rows.
3. The admin maps the inline rows to `StoreListingPayload` objects.
4. The system synchronizes listings through `ProductStoreService`.
5. The system updates existing listings, creates missing ones, and removes deleted ones.
6. The system appends a new price history row only when price or stock status changed.

### Alternate flows

#### A1. Listing row without price

1. The actor fills a listing row but omits the price.
2. The inline formset rejects the submission.

#### A2. Duplicate store rows

1. The actor submits the same store more than once.
2. The service rejects the operation with a validation error.

### Business rules

- Admin store listing management must go through `ProductStoreService`.
- Price history is append-only support data.

## Notes

- `ProductAdmin` is the official manager-facing workflow for product operations.
- Product support admins are secondary technical surfaces, not the preferred business path.
