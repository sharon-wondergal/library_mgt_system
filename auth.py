"""
Librarian authentication.

* Passwords are stored as salted hashes (werkzeug, scrypt) -- never as text.
* The logged-in librarian is kept in Flask's signed session cookie.
* ``login_required`` protects every catalogue page.
* ``admin_required`` protects destructive actions (deleting books).
"""
from functools import wraps
from urllib.parse import urlparse

import click
import mysql.connector
from flask import (Blueprint, abort, flash, redirect, render_template, request,
                   session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash

import db

auth_bp = Blueprint("auth", __name__)

# Used to keep login timing similar whether or not the username exists.
_DUMMY_HASH = generate_password_hash("not-a-real-password")


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("librarian_id"):
            flash("Please sign in to continue.", "warning")
            next_url = request.full_path.rstrip("?") if request.method == "GET" else None
            return redirect(url_for("auth.login", next=next_url))
        return view(*args, **kwargs)
    return wrapped


def admin_required(view):
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if session.get("role") != "admin":
            abort(403, description="Only administrators can delete book records.")
        return view(*args, **kwargs)
    return wrapped


def _safe_next(target):
    """Only allow redirects to paths on this site (prevents open redirects)."""
    if not target or "\\" in target:
        return None
    parsed = urlparse(target)
    if parsed.scheme or parsed.netloc or not target.startswith("/"):
        return None
    return target


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if session.get("librarian_id"):
        return redirect(url_for("books.dashboard"))

    error = None
    username = ""
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if not username or not password:
            error = "Enter both your username and password."
        else:
            user = db.query_one(
                "SELECT librarian_id, username, full_name, password_hash, role "
                "FROM librarian WHERE username = %s",
                (username,),
            )
            stored_hash = user["password_hash"] if user else _DUMMY_HASH
            password_ok = check_password_hash(stored_hash, password)
            if user and password_ok:
                session.clear()
                session.permanent = True
                session["librarian_id"] = user["librarian_id"]
                session["username"] = user["username"]
                session["full_name"] = user["full_name"]
                session["role"] = user["role"]
                flash(f"Welcome back, {user['full_name']}!", "success")
                return redirect(_safe_next(request.args.get("next")) or url_for("books.dashboard"))
            error = "Invalid username or password."

    return render_template("login.html", error=error, username=username), (401 if error else 200)


@auth_bp.post("/logout")
def logout():
    session.clear()
    flash("You have been signed out.", "info")
    return redirect(url_for("auth.login"))


@click.command("create-librarian")
@click.option("--username", prompt=True)
@click.option("--full-name", prompt="Full name")
@click.option("--role", type=click.Choice(["admin", "librarian"]), default="librarian",
              prompt=True, show_default=True)
@click.password_option()
def create_librarian_command(username, full_name, role, password):
    """Add a librarian account (or reset the password of an existing one)."""
    if len(password) < 6:
        raise click.ClickException("Password must be at least 6 characters.")
    try:
        db.execute(
            "INSERT INTO librarian (username, full_name, password_hash, role) "
            "VALUES (%s, %s, %s, %s) "
            "ON DUPLICATE KEY UPDATE full_name = VALUES(full_name), "
            "password_hash = VALUES(password_hash), role = VALUES(role)",
            (username.strip(), full_name.strip(), generate_password_hash(password), role),
        )
    except (mysql.connector.Error, db.DatabaseUnavailable) as exc:
        raise click.ClickException(f"Could not save librarian: {exc}")
    click.secho(f"Librarian '{username}' saved with role '{role}'.", fg="green")
