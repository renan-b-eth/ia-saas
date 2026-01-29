from datetime import datetime
from flask_login import UserMixin
from app.extensions import db

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    company_name = db.Column(db.String(150))
    maps_url = db.Column(db.String(500))
    plan_tier = db.Column(db.String(50), default='free')
    stripe_customer_id = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    full_name = db.Column(db.String(150))
    phone = db.Column(db.String(20))
    avatar_url = db.Column(db.String(500), default='/static/default-avatar.png')
    warnings = db.Column(db.Integer, default=0)
    ban_until = db.Column(db.DateTime, nullable=True)

class Report(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    tool_name = db.Column(db.String(100))
    tool_description = db.Column(db.Text)
    tool_url = db.Column(db.String(500))
    input_data = db.Column(db.Text)
    ai_response = db.Column(db.Text)
    status = db.Column(db.String(20), default="PENDING")
    date_created = db.Column(db.DateTime, default=datetime.utcnow)

class Document(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(200))
    content = db.Column(db.Text)
    file_type = db.Column(db.String(20))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
