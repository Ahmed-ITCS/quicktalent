import logging
import os

from flask import Flask, render_template

import db as database
from auth_utils import hash_password
from config import config

logging.basicConfig(level=logging.INFO)


def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = config.SECRET_KEY
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024

    from routes_admin import bp as admin_bp
    from routes_auth import bp as auth_bp
    from routes_hr import bp as hr_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(hr_bp)
    app.register_blueprint(admin_bp)

    @app.context_processor
    def inject_globals():
        from auth_utils import current_user, is_admin

        return {"current_user": current_user(), "is_admin": is_admin(), "db_mode": config.backend_name}

    @app.route("/")
    def landing():
        stats = None
        try:
            stats = {
                "candidates": database.db.count_candidates(),
                "hrs": database.db.count_users(),
                "contacts": database.db.count_contacts(),
            }
        except Exception:  # noqa: BLE001
            pass
        return render_template("landing.html", stats=stats)

    @app.errorhandler(403)
    def forbidden(_e):
        return render_template("error.html", code=403, message="You don't have access to this page."), 403

    @app.errorhandler(404)
    def not_found(_e):
        return render_template("error.html", code=404, message="Page not found."), 404

    @app.errorhandler(500)
    def server_error(_e):
        return render_template("error.html", code=500, message="Something went wrong on our side."), 500

    # Seed the god account on first boot
    if config.has_god():
        user = database.db.ensure_god(config.GOD_EMAIL, hash_password(config.GOD_PASSWORD))
        app.logger.info("god account ready: %s (role=%s)", user["email"], user["role"])

    app.logger.info(
        "QuickTalent boot: backend=%s base=%s tables=%r sort_field=%r",
        config.backend_name,
        config.AIRTABLE_BASE_ID or "-",
        [config.AIRTABLE_CANDIDATES_TABLE, config.AIRTABLE_HR_TABLE, config.AIRTABLE_CONTACTS_TABLE],
        config.AIRTABLE_SORT_FIELD,
    )

    return app


app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
