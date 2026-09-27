# Catalog rules

## One product, many offers

A product is the package a person swallows from, not the listing that sells it.
The same whey in three stores is one `Product` with three store links. Creating
a second product for the second store splits the ranking.

Search by EAN first: it is the only identifier stores share. Fall back to brand
plus name, remembering that stores rename freely -- "Whey Concentrado 1kg" and
"100% Whey Protein Concentrado (1000g)" are routinely the same product. A
different package size is a different product.

## Flavors and nutrition profiles

Nutrition belongs to a printed label, not to a product. One product can carry
several labels, and several flavors can share one label -- a flavored whey and
its Natural version usually print different tables.

So a profile links one table to the flavors that print it. Two flavors with
identical tables are one profile with two flavors; two flavors with different
tables are two profiles. Never merge tables and never take the highest value
across them -- a concentration is only meaningful next to the serving it was
measured in. Ingredients may differ between flavors that share a table.

## Offers and links

An offer is one unit a store sells, usually one flavor of one size. Link it to
the profile that lists its flavor. Several offers -- one per flavor, or one per
store -- may link to the same profile; the catalog row shows the cheapest. An
offer the store stopped selling is delisted and cannot be linked.

A combo (a kit of several products) has no label of its own: it is built from
its components and links its offers without a profile.

## Kind is structure, category is identity

`kind` says whether a product is simple or a combo. A combo is assembled from
simple products, one level deep, and cannot contain itself. This is orthogonal
to the category, which says what the product is and which active it is ranked
by. Classify by what defines the line (a 3W whey is 3W even if it adds
collagen); record extra components in the composition, not the category.

## What does not belong

Apparel, shakers, bottles, accessories, gift cards -- anything with no
ingestible content. They have no active, so they cannot rank, and they dilute
search for the products that can.

## Units

Type every number exactly as the package prints it, in the unit the field's
label names: net mass, serving and macros in g, sodium in mg, energy in kcal.
A nutrition active row takes the printed amount with its printed unit. Never
convert. Values the catalog cannot convert -- international units, percentages
of a daily value -- carry no concentration and simply do not rank.
