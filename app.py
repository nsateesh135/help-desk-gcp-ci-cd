import os.path
from models import models
from flask import Flask, request, render_template, redirect

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, "helpdesk.db")


app = Flask(__name__)
SQLALCHEMY_DATABASE_URI = os.environ.get(
    'SQLALCHEMY_DATABASE_URI',
    "sqlite:///" + DATABASE
)
app.config['SQLALCHEMY_DATABASE_URI'] = SQLALCHEMY_DATABASE_URI


db = models.db
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
