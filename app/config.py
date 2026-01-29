import os
from datetime import timedelta


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "segredo_master_renan_saas_2026")

    # Database
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///saas.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True, "pool_recycle": 300}

    # HF: /tmp é o único lugar garantido
    UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER", "/tmp/uploads")
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024

    # Sessão
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)

    # Stripe
    STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "sk_live_SUA_CHAVE_AQUI")
    STRIPE_PUBLIC_KEY = os.getenv("STRIPE_PUBLIC_KEY", "pk_live_SUA_CHAVE_AQUI")
    DOMAIN_URL = os.getenv("DOMAIN_URL", "https://renan-b-eth-saas-varejo.hf.space")

    # Mail Namecheap
    MAIL_SERVER = os.getenv("MAIL_SERVER", "mail.privateemail.com")
    MAIL_PORT = int(os.getenv("MAIL_PORT", "465"))
    MAIL_USE_SSL = True
    MAIL_USERNAME = os.getenv("MAIL_USERNAME", "contact@rendey.store")
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD", "@@Dolarizandose2026")
    MAIL_DEFAULT_SENDER = os.getenv("MAIL_DEFAULT_SENDER", "contact@rendey.store")

    # Segurança web
    FORCE_HTTPS = os.getenv("FORCE_HTTPS", "false").lower() == "true"
