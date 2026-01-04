---
description: AlpineJS 3.x Reference
alwaysApply: true
applyTo: "**"
version: 3.x
---

# AlpineJS 3.x Reference

Alpine.js is a rugged, minimal tool for composing behavior directly in your markup. Think of it like jQuery for the modern web. Plugs into the template at an angle.

- [AlpineJS Docs](https://alpinejs.dev/)

## Directives

### State & Initialization

#### `x-data`
Declares a new Alpine component context and its reactive data.

**Syntax**:
```html
<div x-data="{ open: false, count: 0 }">...</div>
<div x-data="dropdown">...</div> <!-- Reusable data via Alpine.data -->
```

#### `x-init`
Runs code when the component is initialized.

**Syntax**:
```html
<div x-init="date = new Date()">...</div>
<div x-init="$watch('open', value => console.log(value))">...</div>
```

**Rules**:
- Can return a function to run as a cleanup callback when the element is removed.

### Binding & Templating

#### `x-bind` (Shorthand: `:`)
Dynamically binds HTML attributes to JavaScript expressions.

**Syntax**:
```html
<div :class="{ 'hidden': !show }"></div>
<input :value="query">
<div :style="{ color: 'red' }"></div>
<button x-bind="bindButton">Bind Group</button>
```

#### `x-text`
Updates the element's text content.

**Syntax**:
```html
<span x-text="count"></span>
```

#### `x-html`
Updates the element's inner HTML.

**Syntax**:
```html
<div x-html="rawHtmlContent"></div>
```

**Warning**: Only use with trusted content to avoid XSS.

#### `x-model`
Two-way data binding for input, textarea, and select elements.

**Syntax**:
```html
<input x-model="search">
<input type="checkbox" x-model="agreed">
```

**Modifiers**:
- `.lazy`: Update data only on `change` (blur).
- `.number`: Cast value to number.
- `.boolean`: Cast value to boolean ('true'/'false').
- `.debounce.<time>ms`: Debounce update (default 250ms).
- `.throttle.<time>ms`: Throttle update.
- `.fill`: Initialize property with element's `value`.
- `.trim`: Trim whitespace.

#### `x-modelable`
Exposes a property to be bound via `x-model` from a parent.

**Syntax**:
```html
<div x-data="{ count: 0 }" x-modelable="count">...</div>
```

#### `x-for`
Iterates over an array to create DOM elements (Required: `<template>`).

**Syntax**:
```html
<template x-for="item in items" :key="item.id">
    <div x-text="item.name"></div>
</template>
```

### Visibility & Effects

#### `x-show`
Toggles `display: none` based on truthiness.

**Syntax**:
```html
<div x-show="open">...</div>
```

**Modifiers**:
- `.important`: Adds `!important` to display style.

#### `x-transition`
Applies classes for enter/leave transitions.

**Syntax**:
```html
<div x-show="open" x-transition>...</div>
<div x-show="open" 
     x-transition:enter="transition ease-out duration-300"
     x-transition:enter-start="opacity-0 scale-90"
     x-transition:enter-end="opacity-100 scale-100"
     x-transition:leave="transition ease-in duration-300"
     x-transition:leave-start="opacity-100 scale-100"
     x-transition:leave-end="opacity-0 scale-90">
</div>
```

#### `x-effect`
Re-runs the expression when reactive dependencies change.

**Syntax**:
```html
<div x-effect="console.log(count)"></div>
```

#### `x-ignore`
Tells Alpine to ignore this element and its children.

**Syntax**:
```html
<div x-ignore>...</div>
```

#### `x-cloak`
Hides element until Alpine initializes (requires CSS: `[x-cloak] { display: none !important; }`).

**Syntax**:
```html
<div x-cloak>...</div>
```

#### `x-teleport`
Moves the element’s content to another part of the DOM (Required: `<template>`).

**Syntax**:
```html
<template x-teleport="body">
    <div class="modal">...</div>
</template>
```

#### `x-if`
Conditionally renders element (removes/adds to DOM) (Required: `<template>`).

**Syntax**:
```html
<template x-if="open">
    <div>...</div>
</template>
```

#### `x-id`
Generates an ID scoped to the component (useful for ARIA).

**Syntax**:
```html
<div x-id="['text-input']">
    <label :for="$id('text-input')">Label</label>
    <input :id="$id('text-input')">
</div>
```

#### `x-ref`
References an element to direct access via `$refs`.

**Syntax**:
```html
<input x-ref="searchField">
<button @click="$refs.searchField.focus()">Focus</button>
```

### Events

#### `x-on` (Shorthand: `@`)
Attaches event listeners.

**Syntax**:
```html
<button @click="open = true">Open</button>
<div @custom-event="handleEvent($event.detail)"></div>
```

**Modifiers**:
- `.prevent`: `event.preventDefault()`.
- `.stop`: `event.stopPropagation()`.
- `.outside`: Event occurred outside the element.
- `.window`: Listen on `window` object.
- `.document`: Listen on `document` object.
- `.once`: Trigger only once.
- `.debounce.<time>ms`: Debounce handler.
- `.throttle.<time>ms`: Throttle handler.
- `.self`: Only if event.target is the element itself.
- `.camel`: Convert dash-case to camelCase.
- `.dot`: Convert dash-case to dot.notation.
- `.passive`: Passive listener (perf optimization).

## Magic Properties

- **`$el`**: The current DOM element.
- **`$refs`**: Object of elements with `x-ref`.
- **$store**: Global store access (`$store.name.property`).
- **`$watch`**: Watch a property: `$watch('open', val => console.log(val))`.
- **`$dispatch`**: Dispatch browser event: `$dispatch('event-name', { data: 123 })`.
- **$nextTick**: Wait for DOM update to finish.
- **`$root`**: The root element of the `x-data` component.
- **`$data`**: Proxy to the data object of the component.
- **`$id`**: Generate scoped ID (`$id('name')`).

## Global Methods (`Alpine.*`)

- **`Alpine.data(name, callback)`**: Define reusable component logic.
- **`Alpine.store(name, object)`**: Define global state.
- **`Alpine.bind(name, object)`**: Define reusable attribute bindings.
- **`Alpine.start()`**: Start Alpine (if importing as module).
