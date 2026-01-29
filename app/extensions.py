from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_mail import Mail
from flask_talisman import Talisman

db = SQLAlchemy()
login_manager = LoginManager()
mail = Mail()

def init_extensions(app):
    db.init_app(app)
    login_manager.init_app(app)
    mail.init_app(app)

    login_manager.login_view = "login"

    # Mantém seu comportamento atual
    Talisman(app, content_security_policy=None, force_https=False)
