from app import create_app
from app.extensions import db
import legacy_app

app = create_app()
legacy_app.register_routes(app)

with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=7860, debug=False)
