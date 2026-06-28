# Frontend Implementation

## Overview

The frontend is a server-rendered web UI using Flask's Jinja2 templating engine. There is no JavaScript framework — all pages are full HTML responses delivered by the server on each request. CSS is hand-written and served as a static file.

---

## Template Structure

Flask looks for templates in the `templates/` directory. All pages inherit from a single base template to share the HTML shell, fonts, and stylesheet link.

```
templates/
├── template.html     ← base template (HTML shell, head, body blocks)
├── index.html        ← ticket list page  (extends template.html)
├── add.html          ← new ticket form   (extends template.html)
└── edit.html         ← edit ticket form  (extends template.html)
```

### Base template — `template.html`

Provides the outer HTML document structure. It defines two Jinja2 blocks that child templates fill in:

| Block | Purpose |
|---|---|
| `{% block head %}` | Page-specific `<title>` and inline `<style>` |
| `{% block body %}` | Page content |

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    {% block head %}{% endblock %}
    <link rel="stylesheet" href="{{ url_for('static', filename='template.css') }}">
</head>
<body>
    {% block body %}{% endblock %}
</body>
</html>
```

`url_for('static', filename='template.css')` is a Flask helper that resolves to the correct URL for static assets regardless of where the app is mounted.

### Child templates

Each page starts with `{% extends 'template.html' %}` and then fills the two blocks.

**Example — index.html:**

```html
{% extends 'template.html' %}

{% block head %}
<title>Support Tickets</title>
<style>/* page-specific styles */</style>
{% endblock %}

{% block body %}
<div class="container">
    {% for ticket in tickets %}
        <div class="card">...</div>
    {% endfor %}
</div>
{% endblock %}
```

The `tickets` variable is injected by the Flask route and iterated with `{% for ... %}`.

---

## Pages

### index.html — Ticket Dashboard

- Receives a list of `Ticket` objects from the `/` route.
- Iterates over them with a Jinja2 `for` loop to render one card per ticket.
- Displays a colour-coded **status badge** using a CSS class derived from the status value:

```html
<span class="badge badge-{{ ticket.status | lower | replace(' ', '-') }}">
    {{ ticket.status }}
</span>
```

The Jinja2 filters `| lower` and `| replace(' ', '-')` convert `"In Progress"` → `badge-in-progress`, matching the CSS class names.

- Priority is similarly colour-coded using `priority-high`, `priority-medium`, `priority-low`.
- Each card has an **Edit** link (GET to `/edit/<id>`) and a **Delete** form (POST to `/delete`).
- The delete button uses an inline `onclick="return confirm(...)"` to prompt the user before submission.

### add.html — New Ticket Form

- A plain HTML form with `method="POST"` and `action="/add"`.
- Fields: title (text), description (text), category (select), priority (select), assignee (text).
- Category and priority use `<select>` dropdowns with fixed option lists.
- Status is **not** shown — it is automatically set to `"Open"` by the backend on creation.
- All fields have the `required` attribute for basic browser-side validation.

### edit.html — Edit Ticket Form

- Same fields as the add form, plus a **Status** dropdown (Open / In Progress / Closed).
- Pre-populated using Jinja2 value interpolation:

```html
<input name="title" value="{{ ticket.title }}" />
```

- Dropdowns use a `{% for %}` loop over a hard-coded list with a `selected` conditional:

```html
{% for s in ['Open', 'In Progress', 'Closed'] %}
<option value="{{ s }}" {% if ticket.status == s %}selected{% endif %}>{{ s }}</option>
{% endfor %}
```

- If the ticket ID does not exist, the route renders the same template with an `error` variable and no `ticket` object, displaying the error message instead of the form.

---

## Stylesheet — `static/template.css`

A single global CSS file served from Flask's `static/` directory. Key design decisions:

| Rule | Purpose |
|---|---|
| `body` | Open Sans font, base 16px, neutral `#666` text |
| `.banner` | Full-width gradient strip (`#6a82fb` → `#fc5c7d`) with centred white heading |
| `.form-holder` | Centred content column, 60% wide, with light border |
| `.card` | Individual ticket card with a subtle box-shadow |
| `input:not([type="radio"])` | Uniform styling for all text/number inputs |
| `select` | Matches input styling — same border, padding, font |
| `.badge-*` | Pill-shaped status indicators with semantic background colours |
| `.priority-*` | Colour-only priority indicators (red / orange / green) |
| `input[type="submit"], .back-btn` | Shared button style with the brand blue (`#6a82fb`) |

Page-specific styles (card layout, edit/delete button placement) are kept in `<style>` blocks inside each template's `{% block head %}` to avoid polluting the global file.

---

## Data Flow: Request to Rendered Page

```
Browser GET /
      │
      ▼
Flask route index()
      │  queries DB: Ticket.query.order_by(id).all()
      ▼
render_template("index.html", tickets=[...])
      │
      ▼
Jinja2 renders template.html + index.html
      │  substitutes {{ ticket.title }}, loops, conditionals
      ▼
Complete HTML string sent back as HTTP 200 response
      │
      ▼
Browser renders the page
```

Form submissions follow the reverse path: browser POSTs form data → Flask route reads `request.form` → updates DB → returns `redirect("/")` → browser issues a fresh GET.
