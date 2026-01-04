---
description: HTMX 2.0 Reference
alwaysApply: true
applyTo: "**"
version: 2.0.x
---

# HTMX 2.0 Reference

HTMX gives you access to AJAX, CSS Transitions, WebSockets and Server Sent Events directly in HTML, using attributes, so you can build modern user interfaces with the simplicity and power of hypertext.

- [HTMX Docs](https://htmx.org/docs/)
- [HTMX Reference](https://htmx.org/reference/)

## Core Attributes

### Request Modifiers
Attributes that control how and when requests are made.

#### `hx-get`, `hx-post`, `hx-put`, `hx-patch`, `hx-delete`
Issues the specified HTTP request to the given URL.

**Syntax**:
```html
<button hx-post="/account/disable">Disable Account</button>
<a hx-get="/blog">Blog</a>
```

**Rules**:
- By default, triggers on `click` for buttons/links and `change` for inputs.
- Validates the form if inside one.

#### `hx-trigger`
Specifies how the request is triggered.

**Syntax**:
```html
<div hx-trigger="{EVENT} {MODIFIERS}"></div>
```

**Modifiers**:
- `once`: Trigger only once.
- `changed`: Trigger only if value changed.
- `delay:<time>`: Debounce trigger (e.g., `delay:500ms`).
- `throttle:<time>`: Throttle trigger (e.g., `throttle:500ms`).
- `from:<selector>`: Listen for event on different element.
- `target:<selector>`: Filter event target.
- `consume`: Stop propagation.
- `queue:<option>`: Determines how to queue events (`first`, `last`, `all`, `none`).

#### `hx-vals`
Adds values to submit with the request.

**Syntax**:
```html
<div hx-vals='{"myVal": "My Value"}'></div>
<div hx-vals='js:{myVal: calculateValue()}'></div>
```

#### `hx-params`
Filters parameters submitted with the request.

**Syntax**:
```html
<div hx-params="*"></div> <!-- All (default) -->
<div hx-params="none"></div> <!-- None -->
<div hx-params="not value"></div> <!-- Exclude specific -->
```

### Response Processing
Attributes that control what happens with the response.

#### `hx-swap`
Controls how the response content is swapped into the DOM.

**Values**:
- `innerHTML` (Default): Replaces the inner HTML of the target.
- `outerHTML`: Replaces the entire target element.
- `textContent`: Replaces text content, escaping HTML.
- `beforebegin`: Inserts response before the target.
- `afterbegin`: Inserts response as the first child.
- `beforeend`: Inserts response as the last child.
- `afterend`: Inserts response after the target.
- `delete`: Deletes the target element (ignores response).
- `none`: Does not append response (useful for OOB).

**Modifiers**:
- `transition:true`: Uses View Transitions API.
- `swap:<time>`: Wait time before swapping.
- `settle:<time>`: Wait time after swapping.
- `scroll:<val>`: Scroll to top/bottom of target.
- `show:<val>`: Scroll element into view.
- `focus-scroll:<bool>`: Auto-scroll on focus (default true).

#### `hx-target`
Specifies the element to swap the response into.

**Syntax**:
```html
<button hx-target="#result">Load</button>
<button hx-target="this">Load into Self</button>
<button hx-target="closest .container">Load into Container</button>
<button hx-target="next .peer">Load into Next Peer</button>
```

#### `hx-select`
Selects a subset of the response HTML to swap.

**Syntax**:
```html
<button hx-select="#main-content">Load Main</button>
```

#### `hx-select-oob`
Selects content from response to swap Out of Band (somewhere else).

**Syntax**:
```html
<button hx-select-oob="#sidebar">Update Sidebar</button>
```

#### `hx-swap-oob`
Mark an element in the *response* to be swapped Out of Band.

**Syntax**:
```html
<div id="alert" hx-swap-oob="true">Saved!</div>
<div id="alert" hx-swap-oob="outerHTML: #other-alert">Saved!</div>
```

### Indicators & Synchronization

#### `hx-indicator`
Specifies element to show during request (via `.htmx-request` class).

**Syntax**:
```html
<button hx-indicator="#spinner">Save</button>
<img id="spinner" class="htmx-indicator" src="/spinner.gif"/>
```

#### `hx-sync`
Coordinates requests between elements.

**Values**:
- `drop`: Drop new requests if one is running.
- `abort`: Abort running request.
- `replace`: Replace running request.
- `queue <first|last|all>`: Queue requests.

**Syntax**:
```html
<form hx-post="/store" hx-sync="this:drop">
    <button>Submit</button>
</form>
```

### History & URL

#### `hx-push-url`
Pushes a new URL into the browser history.

**Syntax**:
```html
<a hx-get="/blog" hx-push-url="true">Blog</a>
<a hx-get="/blog" hx-push-url="/blog/latest">Blog</a>
```

#### `hx-replace-url`
Replaces the current URL in the location bar.

**Syntax**:
```html
<a hx-get="/blog" hx-replace-url="true">Blog</a>
```

### Inheritance Modifiers

#### `hx-boost`
Progressively enhances links and forms to use AJAX.

**Syntax**:
```html
<body hx-boost="true">
    <a href="/blog">Boosted Link</a>
</body>
```

#### `hx-disinherit`
Disables attribute inheritance for children.

**Syntax**:
```html
<div hx-boost="true">
    <div hx-disinherit="hx-boost">
        <a href="/no-ajax">Regular Link</a>
    </div>
</div>
```

## Additional Attributes

- `hx-confirm`: Shows `confirm()` dialog.
- `hx-disable`: Disables HTMX on element.
- `hx-disabled-elt`: adds `disabled` attribute during request.
- `hx-encoding`: `multipart/form-data`.
- `hx-ext`: Enable extensions.
- `hx-headers`: Add custom request headers (`hx-headers='{"X-Token": "123"}'`).
- `hx-history`: `false` to prevent history snapshot.
- `hx-history-elt`: Element to snapshot for history.
- `hx-include`: Include other elements values in request (`hx-include="#other-input"`).
- `hx-preserve`: Keep element unchanged during swap (requires `id`).
- `hx-prompt`: Shows `prompt()` dialog.
- `hx-request`: Config options (`timeout`, `credentials`, `noHeaders`).
- `hx-validate`: Force validation.
- `hx-vars`: Dynamic values (Deprecated, use `hx-vals`).

## CSS Classes

HTMX adds and removes classes to manage state.

- `.htmx-added`: Applied to new content.
- `.htmx-indicator`: Use with `opacity: 0` to hide until request.
- `.htmx-request`: Added to triggering element and `hx-indicator` during request.
- `.htmx-settling`: Applied during settle phase.
- `.htmx-swapping`: Applied during swap phase.

**Indicator CSS Example**:
```css
.htmx-indicator {
    opacity: 0;
    transition: opacity 200ms ease-in;
}
.htmx-request .htmx-indicator {
    opacity: 1;
}
.htmx-request.htmx-indicator {
    opacity: 1;
}
```

## Request Headers (Sent by HTMX)

- `HX-Request`: `true`
- `HX-Trigger`: ID of triggering element.
- `HX-Trigger-Name`: Name of triggering element.
- `HX-Target`: ID of target element.
- `HX-Current-URL`: Current URL of browser.
- `HX-Boosted`: `true` if boosted.
- `HX-Prompt`: User response to `hx-prompt`.

## Response Headers (Handled by HTMX)

Server can send these headers to trigger actions.

- `HX-Location`: Client-side redirect (AJAX).
- `HX-Push-Url`: Push URL to history.
- `HX-Redirect`: Full page redirect.
- `HX-Refresh`: Full page refresh.
- `HX-Replace-Url`: Replace URL.
- `HX-Reswap`: Override `hx-swap`.
- `HX-Retarget`: Override `hx-target`.
- `HX-Reselect`: Override `hx-select`.
- `HX-Trigger`: Trigger event (`{"event": "data"}`).
- `HX-Trigger-After-Swap`: Trigger event after swap.
- `HX-Trigger-After-Settle`: Trigger event after settle.

## Events

HTMX emits distinct events you can listen to.

- `htmx:configRequest`: Configure request (headers, params).
- `htmx:beforeRequest`: Before AJAX send.
- `htmx:afterRequest`: After AJAX complete.
- `htmx:beforeSwap`: Before content swap.
- `htmx:afterSwap`: After content swap.
- `htmx:afterSettle`: After settle.
- `htmx:load`: New element initialized.
- `htmx:confirm`: For custom confirmation logic.
- `htmx:responseError`: HTTP error.
- `htmx:sendError`: Network error.
- `htmx:timeout`: Timeout.
- `htmx:oobAfterSwap`: Out of Band swap finished.
