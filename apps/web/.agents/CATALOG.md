# Public catalog table

- The catalog uses `@tanstack/vue-table` v8, with manual server filtering,
  sorting and pagination. `/api/catalog/products/` remains the source of data.
- `useCatalogTable` owns TanStack global search, column filters, sorting,
  pagination and column visibility. `useCatalogQuery` only reads REST data.
- Never sort/filter only the current API page or invent API filters. The only
  sortable columns are price, price per active, concentration and total active.
  Filters cover brand, price, price per active and concentration, plus search.
- Search and column filters are debounced together; restart pagination when
  the debounced query changes. The API accepts 12, 24 or 48 rows per page.
- API `pricePerActive` and its filter limits remain per gram of the selected
  active ingredient. Display price per **100 g of active**, converting before
  rounding; convert UI filter bounds back with division by 100.
- Row identity remains product ID plus nutrition profile ID. Nutrition profiles
  with distinct flavors/nutrition labels must not collapse into a product row.
- Column visibility is independent of the API query. Hiding a column must not
  discard its active filter or sorting. Clearing filters preserves the scenario
  and column visibility.
- Keep offer conditions (payment, coupons, cashback, route instructions),
  incomplete optimization status and seller-selection warnings visible.
- Public catalog has a compact table and filter and sort menus in each column header. There are no
  card modes, filter drawers, product photographs or product comparison flows.
- Keep the header full width: logo at the far left, name beside it, theme and
  bomb alert button at right. Keep the alert button text visible on mobile. No navigation tabs or public login.
- The table grows with its rows; horizontal overflow is only for narrow screens.
- Column filter controls remain available for empty and loading results.
- Comparison dropdowns use BaseSelect for rounded fields and popup menus.
- Start with a discreet two-field comparison bar: current active and supported
  payment scenarios. No search or column picker in this bar. Column visibility is on the left
  above the table, with page size on the right. The API currently
  returns one active, so do not invent additional choices. Omit the title,
  subtitle and market badge.
- Snapshots, CDN publishing and client-side full-catalog processing are deferred.

## Sources

- Vue adapter: https://tanstack.com/table/v8/docs/framework/vue/vue-table
- Filtering: https://tanstack.com/table/v8/docs/guide/column-filtering
- Sorting: https://tanstack.com/table/v8/docs/guide/sorting
- Pagination: https://tanstack.com/table/v8/docs/guide/pagination
