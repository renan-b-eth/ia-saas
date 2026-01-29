from datetime import datetime
from app.extensions import db


class Report(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

    tool_name = db.Column(db.String(100))
    tool_description = db.Column(db.Text)
    tool_url = db.Column(db.String(500))

    input_data = db.Column(db.Text)
    ai_response = db.Column(db.Text)

    status = db.Column(db.String(20), default="PENDING")
    date_created = db.Column(db.DateTime, default=datetime.utcnow)
