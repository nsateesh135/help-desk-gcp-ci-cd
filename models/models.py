from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class Ticket(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100))
    description = db.Column(db.String(500))
    category = db.Column(db.String(50))
    priority = db.Column(db.String(10))
    status = db.Column(db.String(20))
    assignee = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
