---
description: daisyUI 5 Reference
alwaysApply: true
applyTo: "**"
version: 5.5.x
---

# daisyUI 5 Reference

- [daisyUI Docs](https://daisyui.com)

## Global Modifiers
- **Colors**: `primary`, `secondary`, `accent`, `neutral`, `info`, `success`, `warning`, `error`.
- **Sizes**: `xs`, `sm`, `md`, `lg`, `xl`.
- **States**: `active`, `disabled`, `hover`, `focus`.

## Components

### Actions
- **Button** (`btn`): `btn-{color}`, `btn-outline`, `btn-ghost`, `btn-link`, `btn-wide`, `btn-block`, `btn-circle`, `btn-square`.
- **Dropdown** (`dropdown`): `dropdown-content`, `dropdown-{dir}`, `dropdown-hover`, `dropdown-open`.
- **Modal** (`modal`): `modal-box`, `modal-action`, `modal-backdrop`. Open via `<dialog>` `.showModal()`.
- **Swap** (`swap`): `swap-on`, `swap-off`, `swap-rotate`, `swap-flip`.
- **Theme Controller**: `<input type="checkbox" class="theme-controller" value="theme-name"/>`

### Data Display
- **Accordion** (`collapse`): `collapse-title`, `collapse-content`, `collapse-arrow`, `collapse-plus`.
- **Alert** (`alert`): `alert-{color}`, `alert-soft`. Structure: `svg` + `span`.
- **Avatar** (`avatar`): `avatar-group`, `online`, `offline`, `placeholder`. Mask with `mask mask-{shape}`.
- **Badge** (`badge`): `badge-{color}`, `badge-{size}`, `badge-outline`, `badge-soft`.
- **Card** (`card`): `card-body`, `card-title`, `card-actions`, `card-bordered`, `card-compact`, `image-full`.
- **Carousel** (`carousel`): `carousel-item`, `carousel-center`, `carousel-vertical`.
- **Chat** (`chat`): `chat-start`, `chat-end`, `chat-bubble`, `chat-header`, `chat-footer`.
- **Countdown**: `<span class="countdown"><span style="--value:10;"></span></span>`
- **Diff** (`diff`): `diff-item-1`, `diff-item-2`, `diff-resizer`.
- **Kbd** (`kbd`): `kbd-{size}`.
- **Loading** (`loading`): `loading-spinner`, `loading-dots`, `loading-ring`, `loading-ball`, `loading-infinity`.
- **Progress** (`progress`): `progress-{color}`. `<progress value="50" max="100">`.
- **Radial Progress**: `radial-progress`. `<div style="--value:70;">`.
- **Stat** (`stats`): `stat`, `stat-title`, `stat-value`, `stat-desc`, `stat-figure`. `stats-vertical`.
- **Table** (`table`): `table-zebra`, `table-pin-rows`, `table-pin-cols`, `table-{size}`.
- **Timeline** (`timeline`): `timeline-start`, `timeline-middle`, `timeline-end`, `timeline-compact`, `timeline-snap-icon`.
- **Toast** (`toast`): `toast-{dir}` (e.g. `toast-top toast-end`).
- **Tooltip** (`tooltip`): `tooltip-{dir}`, `tooltip-{color}`, `data-tip="Text"`.

### Form
- **Checkbox** (`checkbox`): `checkbox-{color}`, `checkbox-{size}`.
- **File Input** (`file-input`): `file-input-bordered`, `file-input-{color}`.
- **Input** (`input`): `input-bordered`, `input-ghost`, `input-{color}`.
- **Radio** (`radio`): `radio-{color}`, `radio-{size}`.
- **Range** (`range`): `range-{color}`, `range-{size}`.
- **Rating** (`rating`): `mask mask-star-2`.
- **Select** (`select`): `select-bordered`, `select-{color}`.
- **Textarea** (`textarea`): `textarea-bordered`, `textarea-{color}`.
- **Toggle** (`toggle`): `toggle-{color}`, `toggle-{size}`.

### Layout
- **Divider** (`divider`): `divider-horizontal`, `divider-vertical`.
- **Drawer** (`drawer`): `drawer-toggle`, `drawer-content`, `drawer-side`, `drawer-overlay`, `drawer-end`.
- **Footer** (`footer`): `footer-center`. Group with `<nav>`.
- **Hero** (`hero`): `hero-content`, `hero-overlay`.
- **Indicator** (`indicator`): `indicator-item`, `indicator-{dir}`.
- **Join** (`join`): `join-item`, `join-vertical`.
- **Mask** (`mask`): `mask-squircle`, `mask-heart`, `mask-hexagon`, `mask-circle`.
- **Navbar** (`navbar`): `navbar-start`, `navbar-center`, `navbar-end`.
- **Stack** (`stack`): Stacked elements.

### Navigation
- **Breadcrumbs** (`breadcrumbs`): `<ul><li><a>...</a></li></ul>`
- **Link** (`link`): `link-hover`, `link-{color}`.
- **Menu** (`menu`): `menu-vertical`, `menu-horizontal`, `menu-{size}`, `menu-dropdown`.
- **Steps** (`steps`): `step`, `step-primary`, `step-vertical`.
- **Tab** (`tabs`): `tab`, `tab-active`, `tab-lifted`, `tab-bordered`, `tab-content`.
