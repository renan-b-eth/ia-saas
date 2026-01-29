from datetime import datetime
from app.extensions import db


class Document(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

    title = db.Column(db.String(200))
    content = db.Column(db.Text)
    file_type = db.Column(db.String(20))

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
