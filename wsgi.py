"""Entry point: `python wsgi.py` for local dev, `gunicorn wsgi:app` in production."""
import os

from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", 5000)), debug=True)
