from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_mail import Mail
from flask_talisman import Talisman

db = SQLAlchemy()
login_manager = LoginManager()
mail = Mail()
talisman = None


def init_extensions(app):
    global talisman

    db.init_app(app)

    login_manager.init_app(app)
    login_manager.login_view = "login"

    mail.init_app(app)

    # HF geralmente não força https internamente
    talisman = Talisman(app, content_security_policy=None, force_https=app.config.get("FORCE_HTTPS", False))
