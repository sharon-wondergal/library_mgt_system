"""
Library Book Management System -- application entry point.

Run (from this folder):
    flask init-db          # first time only: creates tables + sample data
    python app.py          # then open http://127.0.0.1:5000
"""
import hmac
import os
import secrets
from datetime import date

import mysql.connector
from flask import Flask, render_template, request, session, url_for

import db
from auth import auth_bp, create_librarian_command
from books import books_bp
from config import Config
from icons import icon


def get_csrf_token():
    """One random token per session, embedded in every form we render."""
    token = session.get("csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["csrf_token"] = token
    return token


def url_with(**changes):
    """Current URL with some query arguments changed (used by pagination)."""
    args = request.args.to_dict()
    args.update(changes)
    args = {k: v for k, v in args.items() if v not in (None, "")}
    return url_for(request.endpoint, **(request.view_args or {}), **args)


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    app.register_blueprint(auth_bp)
    app.register_blueprint(books_bp)
    app.cli.add_command(create_librarian_command)

    app.jinja_env.globals.update(icon=icon, csrf_token=get_csrf_token, url_with=url_with)

    @app.context_processor
    def inject_globals():
        return {
            "current_year": date.today().year,
            "low_stock": app.config["LOW_STOCK_THRESHOLD"],
            "is_admin": session.get("role") == "admin",
        }

    # ------------------------------------------------------------------
    # CSRF protection: every POST must carry the session's token, so other
    # websites cannot submit forms (e.g. delete a book) on a user's behalf.
    # ------------------------------------------------------------------
    @app.before_request
    def csrf_protect():
        if request.method == "POST":
            expected = session.get("csrf_token")
            sent = request.form.get("csrf_token") or request.headers.get("X-CSRFToken")
            if not expected or not sent or not hmac.compare_digest(expected, sent):
                return render_template(
                    "error.html", code=400, title="Form expired",
                    message="Your form session has expired. Please go back, reload "
                            "the page and try again."), 400

    # ------------------------------------------------------------------
    # Friendly error pages
    # ------------------------------------------------------------------
    def error_page(code, title, default_message):
        def handler(err):
            message = getattr(err, "description", None) or default_message
            return render_template("error.html", code=code, title=title, message=message), code
        return handler

    app.register_error_handler(403, error_page(403, "Access denied",
                               "You do not have permission to do that."))
    app.register_error_handler(404, error_page(404, "Page not found",
                               "The page you requested could not be found."))
    app.register_error_handler(405, error_page(405, "Method not allowed",
                               "That action is not allowed here."))

    @app.errorhandler(db.DatabaseUnavailable)
    def database_unavailable(err):
        app.logger.error("Database unavailable: %s", err)
        message = ("The library database cannot be reached right now. Make sure the "
                   "MySQL server is running and the settings in config.py are correct, "
                   "then try again.")
        if err.errno == 1049:  # unknown database
            message = ("The library database does not exist yet. Run 'flask init-db' "
                       "in the project folder, then reload this page.")
        elif err.errno == 1045:  # access denied
            message = ("MySQL refused the username or password in config.py "
                       "(DB_USER / DB_PASSWORD). Update them and restart the app.")
        return render_template("error.html", code=503, title="Database unavailable",
                               message=message, show_retry=True), 503

    @app.errorhandler(mysql.connector.Error)
    def database_error(err):
        app.logger.exception("Database error: %s", err)
        message = "A database error occurred while processing your request."
        if err.errno == 1146:  # table doesn't exist
            message = ("The library tables have not been created yet. "
                       "Run 'flask init-db' in the project folder, then reload this page.")
        elif err.errno == 1049:  # unknown database
            message = ("The library database does not exist yet. "
                       "Run 'flask init-db' in the project folder, then reload this page.")
        return render_template("error.html", code=500, title="Database error",
                               message=message, show_retry=True), 500

    @app.errorhandler(500)
    def internal_error(err):
        return render_template("error.html", code=500, title="Something went wrong",
                               message="An unexpected error occurred. Please try again."), 500

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", 5000)),
            debug=os.environ.get("FLASK_DEBUG") == "1")
