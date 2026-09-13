# Catalog rules

## One product, many offers

A product is the thing a person swallows, not the listing that sells it. The
same whey in three stores is one `Product` with three store listings and three
offers. Creating a second product for the second store makes both unrankable,
because price per gram is then computed against a split catalog.

Search by EAN first: it is the only identifier stores share. Fall back to brand
plus name, remembering that stores rename freely -- "Whey Concentrado 1kg" and
"100% Whey Protein Concentrado (1000g)" are routinely the same product.

## Flavours and nutrition profiles

Nutrition belongs to a printed label, not to a product. One product can carry
several labels, and several flavours can share one label.

So a `ProductNutrition` profile links one nutrition table to the flavours that
print it. Two flavours with identical tables are one profile with two flavours;
two flavours with different tables are two profiles. Never merge tables and
never take the highest value across them -- a concentration is only meaningful
next to the serving it was measured in.

## Kind is structure, category is identity

`kind` says whether a product is simple or a combo. A combo is assembled from
simple products, one level deep, and cannot contain itself. This is orthogonal
to `Category`, which says what the product is and which active it is ranked by.

## What does not belong

Apparel, shakers, bottles, accessories, gift cards -- anything with no
ingestible content. They have no active, so they cannot rank, and they dilute
search for the products that can.

## Units

Masses are stored in one canonical unit and converted at the boundary. Send a
value together with its unit and let the server canonicalize; never convert
first. Values the catalog cannot convert -- international units, percentages of
a daily value -- carry no concentration and simply do not rank.
