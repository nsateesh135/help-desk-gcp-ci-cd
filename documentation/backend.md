# Backend Implementation

## Overview

The backend is a Python Flask application with SQLAlchemy as the ORM layer. It follows the MVC pattern: models live in `models/models.py`, routes (controllers) in `app.py`, and views in `templates/`. The database is SQLite by default but can be swapped to any SQLAlchemy-supported engine via an environment variable.

---

## File Structure

```
app.py              ← Flask app, configuration, route handlers
create_db.py        ← One-time script to initialise the database schema
models/
├── __init__.py
└── models.py       ← SQLAlchemy db instance and Ticket model
```

---

## Application Bootstrap — `app.py`

```python
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
    'SQLALCHEMY_DATABASE_URI',
    "sqlite:///" + DATABASE
)
db = models.db
db.init_app(app)
db.app = app
```

Key points:

- `Flask(__name__)` creates the app using the current module as the root for template and static file discovery.
- The database URI is read from the `SQLALCHEMY_DATABASE_URI` environment variable. If not set, it falls back to a local SQLite file (`helpdesk.db`) next to `app.py`. This makes the app portable: no code changes are needed to point it at a different database in a different environment.
- `db.init_app(app)` and `db.app = app` wire the SQLAlchemy instance (defined in `models.py`) to the Flask app. `db.app = app` is needed so that `db` can be used outside of a request context (e.g., in `create_db.py` and tests).

---

## Data Model — `models/models.py`

```python
class Ticket(db.Model):
    id          = db.Column(db.Integer, primary_key=True)
    title       = db.Column(db.String(100))
    description = db.Column(db.String(500))
    category    = db.Column(db.String(50))
    priority    = db.Column(db.String(10))   # Low | Medium | High
    status      = db.Column(db.String(20))   # Open | In Progress | Closed
    assignee    = db.Column(db.String(50))
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)
```

| Column | Type | Notes |
|---|---|---|
| `id` | Integer | Auto-incrementing primary key |
| `title` | String(100) | Short summary of the issue |
| `description` | String(500) | Full description of the problem |
| `category` | String(50) | Bug / Feature Request / Access / Hardware / Other |
| `priority` | String(10) | Low / Medium / High |
| `status` | String(20) | Defaults to `Open`; editable to `In Progress` or `Closed` |
| `assignee` | String(50) | Name of the person responsible |
| `created_at` | DateTime | Set automatically at insert time via `default=datetime.utcnow` |

`db.Model` maps this class to a `ticket` table in the configured database. SQLAlchemy generates the SQL DDL from the column definitions.

### Database Initialisation

`create_db.py` is a one-time setup script:

```python
from app import app, db
with app.app_context():
    db.create_all()
```

`db.create_all()` inspects all registered `db.Model` subclasses and issues `CREATE TABLE IF NOT EXISTS` statements. It is safe to run multiple times.

---

## Route Handlers

### GET `/` — List tickets

```python
@app.route("/")
def index():
    tickets = models.Ticket.query.order_by(models.Ticket.id).all()
    return render_template("index.html", tickets=tickets)
```

Fetches all tickets ordered by ID ascending. Passes the list to the template as `tickets`.

---

### GET/POST `/add` — Create a ticket

```python
@app.route("/add", methods=["POST", "GET"])
def add():
    if request.method == "POST":
        obj = models.Ticket(
            title=form_data["title"],
            ...
            status="Open",      # hardcoded — new tickets always start as Open
        )
        db.session.add(obj)
        db.session.commit()
        return redirect("/")
    else:
        return render_template("add.html")
```

- `GET` renders the blank form.
- `POST` reads `request.form`, constructs a `Ticket` object, persists it, and redirects back to the dashboard (Post/Redirect/Get pattern — prevents duplicate submissions on browser refresh).
- `status` is hardcoded to `"Open"` — users cannot set the initial status.

---

### POST `/delete` — Delete a ticket

```python
@app.route("/delete", methods=["POST"])
def delete():
    id = request.form["ticket_id"]
    obj = models.Ticket.query.filter_by(id=int(id)).first()
    if obj:
        db.session.delete(obj)
        db.session.commit()
        return redirect("/")
    else:
        return render_template("index.html", error="Sorry, the ticket does not exist.")
```

- Only accepts `POST` — no accidental deletion via a bookmarked URL.
- `filter_by(id=...).first()` returns `None` if the ticket does not exist rather than raising an exception, allowing a graceful error message.

---

### GET/POST `/edit/<int:id>` — Edit a ticket

```python
@app.route("/edit/<int:id>", methods=["GET", "POST"])
def edit(id):
    obj = models.Ticket.query.filter_by(id=int(id)).first()
    if obj:
        if request.method == "POST":
            obj.title = form_data["title"]
            ...
            obj.status = form_data["status"]   # status is editable here
            db.session.commit()
            return redirect("/")
        else:
            return render_template("edit.html", ticket=obj)
    else:
        return render_template("edit.html", error="Sorry, the ticket does not exist.")
```

- `<int:id>` in the route pattern is a URL converter — Flask casts the segment to an integer before passing it to the function. A non-integer URL returns a 404 automatically.
- On `GET`, the existing object is passed to the template so the form renders pre-filled.
- On `POST`, the existing object's attributes are updated in-place. SQLAlchemy tracks the changes and issues an `UPDATE` statement on `commit()`.
- Unlike `/add`, the status field is user-editable here — this is the workflow transition point.

---

## Error Handling

Errors are handled inline rather than with a global error handler, keeping each route self-contained:

```python
try:
    db.session.commit()
    return redirect("/")
except Exception:
    return "There was an error"
```

Database errors (constraint violations, connection issues) return a plain text error string. Legitimate "not found" cases return a rendered template with an `error` variable.

---

## Entry Point

```python
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
```

- Binds to `0.0.0.0` so the app is reachable from outside the container.
- Port is read from the `PORT` environment variable (GCP Cloud Run sets this automatically), defaulting to `8080`.
- This block is skipped when a WSGI server (like gunicorn) imports `app` directly. For this project, the Docker `CMD` runs `python app.py` directly, so Flask's built-in server handles requests.

---

## Environment Variables

| Variable | Default | Purpose |
|---|---|---|
| `SQLALCHEMY_DATABASE_URI` | `sqlite:///helpdesk.db` | Database connection string |
| `PORT` | `8080` | Port the app listens on |

To use a Cloud SQL (PostgreSQL) instance in production, set:

```
SQLALCHEMY_DATABASE_URI=postgresql+psycopg2://user:pass@/dbname?host=/cloudsql/PROJECT:REGION:INSTANCE
```

No code changes are required.
