# Catalog rules

## One product, many offers

A product is the package a person swallows from, not the listing that sells it.
The same whey in three stores is one `Product` with three store links. Creating
a second product for the second store splits the ranking.

Search by EAN first: it is the only identifier stores share. Fall back to brand
plus name, remembering that stores rename freely -- "Whey Concentrado 1kg" and
"100% Whey Protein Concentrado (1000g)" are routinely the same product. A
different package size is a different product.

## Flavors and nutrition tables

Nutrition belongs to a printed label, and a product has exactly one. Flavors
whose tables are identical are one product listing all of them; a flavor whose
table differs is a separate product, even when the store sells both on one
page -- the Natural and the flavored version of a whey usually are. Never merge
tables and never take the highest value across them: a concentration is only
meaningful next to the serving it was measured in. Ingredients may differ
between flavors that share a table.

## Offers and links

An offer is one unit a store sells, usually one flavor of one size. Link it to
the product whose table that flavor prints. Several offers -- one per flavor,
or one per store -- may link to the same product; the catalog shows the
cheapest. A product can take its offers before its table is read; once the
table lists flavors, only offers of those flavors fit. An offer the store
stopped selling is delisted and cannot be linked.

A combo (a kit of several products) has no table of its own: it is built from
its components and takes kit offers, whatever flavors they list.

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
