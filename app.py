import os.path
from models import models
from flask import Flask, request, render_template, redirect

BASE_DIR = os.path.dirname(os.path.abspath(__file__) )
DATABASE = os.path.join(BASE_DIR, "helpdesk.db")


app = Flask(__name__)
SQLALCHEMY_DATABASE_URI = os.environ.get(
    'SQLALCHEMY_DATABASE_URI',
    "sqlite:///" + DATABASE
)
app.config['SQLALCHEMY_DATABASE_URI'] = SQLALCHEMY_DATABASE_URI

""" 
db = models.db
This line grabs an already-created SQLAlchemy instance (named db) from your models.py file and assigns it to a variable named db in your current file. It says: "Use the database object that was created inside models.py."

db.init_app(app)
This connects your database instance to your specific Flask web app (app). It tells SQLAlchemy about your database configurations (like SQLALCHEMY_DATABASE_URI) so it knows how and where to open database connections when the server handles requests

db.app = app
This forcibly binds your Flask app instance directly onto the db object. In older versions of Flask-SQLAlchemy (pre-v3.0), developers used this line so they wouldn't have to run code inside an application context (e.g., with app.app_context():)

db.app = app is obsolete and bad practice: Modern Flask-SQLAlchemy handles app contexts differently. Explicitly setting db.app is deprecated and will throw warnings or errors in current versions of Flask.
"""


db = models.db
# Initialize SQLAlchemy with the app
db.init_app(app)
db.app = app


@app.route("/")
def index():
    tickets = models.Ticket.query.order_by(models.Ticket.id).all()
    return render_template("index.html", tickets=tickets)


@app.route("/add", methods=["POST", "GET"])
def add():
    if request.method == "POST":
        form_data = request.form
        obj = models.Ticket(
            title=form_data["title"],
            description=form_data["description"],
            category=form_data["category"],
            priority=form_data["priority"],
            status="Open",
            assignee=form_data["assignee"],
        )
        try:
            db.session.add(obj)
            db.session.commit()
            return redirect("/")
        except Exception:
            return "There was an error"
    else:
        return render_template("add.html")


@app.route("/delete", methods=["POST"])
def delete():
    if request.method == "POST":
        id = request.form["ticket_id"]
        obj = models.Ticket.query.filter_by(id=int(id)).first()
        if obj:
            try:
                db.session.delete(obj)
                db.session.commit()
                return redirect("/")
            except Exception as e:
                print(e)
                return "There was an error"
        else:
            return render_template(
                "index.html", error="Sorry, the ticket does not exist."
            )


@app.route("/edit/<int:id>", methods=["GET", "POST"])
def edit(id):
    obj = models.Ticket.query.filter_by(id=int(id)).first()
    if obj:
        if request.method == "POST":
            form_data = request.form
            obj.title = form_data["title"]
            obj.description = form_data["description"]
            obj.category = form_data["category"]
            obj.priority = form_data["priority"]
            obj.status = form_data["status"]
            obj.assignee = form_data["assignee"]
            try:
                db.session.commit()
                return redirect("/")
            except Exception:
                return "There was an error"
        else:
            return render_template("edit.html", ticket=obj)
    else:
        return render_template(
            "edit.html", error="Sorry, the ticket does not exist.")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
