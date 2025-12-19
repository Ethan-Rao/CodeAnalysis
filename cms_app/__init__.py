from __future__ import annotations

from flask import Flask

from .views import cms_bp


def create_app() -> Flask:
    app = Flask(__name__)

    # Keep it simple for v1; can move to env var later.
    app.config.from_object("cms_app.config.Config")

    app.register_blueprint(cms_bp, url_prefix="/cms")
    return app
