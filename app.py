from app import create_app
from app.extensions import db

app = create_app()

# Importa o sistema antigo para registrar rotas no mesmo app
import legacy_app  # noqa: F401

with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=7860, debug=False)
