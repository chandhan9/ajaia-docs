"""Ajaia Docs: application factory."""
import os
import secrets
from datetime import timedelta

from flask import Flask, jsonify, send_from_directory
from werkzeug.exceptions import HTTPException, RequestEntityTooLarge

from . import db
from .api import bp as api_bp

STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")


def create_app(config: dict | None = None) -> Flask:
    app = Flask(__name__, static_folder=STATIC_DIR, static_url_path="/static")
    app.config.update(
        DATABASE_PATH=os.environ.get("DATABASE_PATH", os.path.join("data", "ajaia_docs.db")),
        # Set SECRET_KEY in production so sessions survive restarts.
        SECRET_KEY=os.environ.get("SECRET_KEY") or secrets.token_hex(32),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.environ.get("SESSION_COOKIE_SECURE", "0") == "1",
        PERMANENT_SESSION_LIFETIME=timedelta(days=7),
        MAX_CONTENT_LENGTH=3 * 1024 * 1024,  # hard cap on any request body
        SEED_DEMO_DATA=os.environ.get("SEED_DEMO_DATA", "1") == "1",
    )
    if config:
        app.config.update(config)

    db_dir = os.path.dirname(app.config["DATABASE_PATH"])
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
    db.init_db(app)
    app.teardown_appcontext(db.close_db)
    app.register_blueprint(api_bp)

    @app.errorhandler(RequestEntityTooLarge)
    def _too_large(_e):
        return jsonify({"error": "Upload is too large."}), 413

    @app.errorhandler(HTTPException)
    def _http_error(e):
        return jsonify({"error": e.description}), e.code

    @app.get("/healthz")
    def health():
        return {"ok": True}

    @app.get("/")
    def index():
        return send_from_directory(STATIC_DIR, "index.html")

    return app
