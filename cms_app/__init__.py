from __future__ import annotations

from flask import Flask

from .views import cms_bp


def create_app() -> Flask:
    app = Flask(__name__)

    # Keep it simple for v1; can move to env var later.
    app.config.from_object("cms_app.config.Config")

    app.register_blueprint(cms_bp, url_prefix="/cms")

    @app.template_filter("intcomma")
    def _intcomma(value):
        try:
            if value is None:
                return ""
            return f"{int(float(value)):,}"
        except Exception:
            return str(value)

    @app.template_filter("currency")
    def _currency(value):
        try:
            if value is None:
                return ""
            return f"${float(value):,.0f}"
        except Exception:
            return str(value)

    return app
