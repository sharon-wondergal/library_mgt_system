"""
Book catalogue: dashboard and all CRUD operations.

Route map
---------
GET        /                         dashboard (statistics)
GET        /books                    list / search / filter / sort / paginate   (Read)
GET, POST  /books/add                add a book                                 (Create)
GET        /books/<id>               details of one book                        (Read)
GET, POST  /books/<id>/edit          edit a book                                (Update)
POST       /books/<id>/quantity      quick stock adjustment (+ / - / set)       (Update)
GET, POST  /books/<id>/delete        confirm + delete (admins only)             (Delete)
GET        /api/isbn-check           JSON: is this ISBN valid and unused?
"""
import math

import mysql.connector
from flask import (Blueprint, abort, current_app, flash, jsonify, redirect,
                   render_template, request, url_for)
from mysql.connector import errorcode

import db
from auth import admin_required, login_required
from validators import is_valid_isbn, normalize_isbn, validate_book

books_bp = Blueprint("books", __name__)

BOOK_COLUMNS = ("book_id, title, author, isbn, category, publisher, publication_year, "
                "quantity, shelf_location, created_at, updated_at")

# Whitelisted ORDER BY clauses -- the user picks a key, never raw SQL.
SORT_OPTIONS = {
    "title":    ("Title (A-Z)",         "title ASC, book_id ASC"),
    "author":   ("Author (A-Z)",        "author ASC, title ASC"),
    "newest":   ("Recently added",      "created_at DESC, book_id DESC"),
    "year":     ("Publication year",    "publication_year DESC, title ASC"),
    "quantity": ("Copies (low first)",  "quantity ASC, title ASC"),
}

# MySQL / MariaDB error numbers for a violated CHECK constraint.
CHECK_CONSTRAINT_ERRORS = {3819, 4025}


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def get_book_or_404(book_id):
    book = db.query_one(f"SELECT {BOOK_COLUMNS} FROM book WHERE book_id = %s", (book_id,))
    if book is None:
        abort(404, description="That book does not exist or has already been deleted.")
    return book


def all_categories():
    rows = db.query_all("SELECT DISTINCT category FROM book ORDER BY category")
    return [r["category"] for r in rows]


def canonical_category(category):
    """Reuse the existing spelling of a category ('science' -> 'Science')."""
    existing = db.query_scalar("SELECT category FROM book WHERE category = %s LIMIT 1", (category,))
    return existing or category


def isbn_taken(isbn, exclude_id=None):
    sql, params = "SELECT book_id FROM book WHERE isbn = %s", [isbn]
    if exclude_id is not None:
        sql += " AND book_id <> %s"
        params.append(exclude_id)
    return db.query_scalar(sql, tuple(params)) is not None


def escape_like(text):
    """Escape LIKE wildcards so a search for '50%' means a literal 50%."""
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def book_to_form(book):
    """Convert a DB row into string values for pre-filling a form."""
    return {k: ("" if v is None else str(v)) for k, v in book.items()}


def database_rule_errors(exc):
    """Translate constraint violations into friendly field errors.

    The application validates first, so these only fire in rare cases
    (e.g. two librarians saving the same ISBN at the same instant).
    """
    if exc.errno == errorcode.ER_DUP_ENTRY:
        return {"isbn": "A book with this ISBN already exists in the catalogue."}
    if exc.errno in CHECK_CONSTRAINT_ERRORS:
        return {"quantity": "The database rejected these values (quantity must be 0 or "
                            "more and the year must be realistic)."}
    raise exc


def book_params(data):
    return (data["title"], data["author"], data["isbn"], data["category"], data["publisher"],
            data["publication_year"], data["quantity"], data["shelf_location"])


# --------------------------------------------------------------------------
# Dashboard
# --------------------------------------------------------------------------
@books_bp.route("/")
@login_required
def dashboard():
    low = current_app.config["LOW_STOCK_THRESHOLD"]
    stats = db.query_one(
        "SELECT COUNT(*) AS total_titles, "
        "       COALESCE(SUM(quantity), 0) AS total_copies, "
        "       COUNT(DISTINCT category) AS total_categories, "
        "       COALESCE(SUM(quantity = 0), 0) AS out_of_stock, "
        "       COALESCE(SUM(quantity BETWEEN 1 AND %s), 0) AS low_stock "
        "FROM book",
        (low,),
    )
    stats = {k: int(v) for k, v in stats.items()}  # SUM() returns Decimal

    categories = db.query_all(
        "SELECT category, COUNT(*) AS titles, COALESCE(SUM(quantity), 0) AS copies "
        "FROM book GROUP BY category ORDER BY titles DESC, category ASC"
    )
    max_titles = max((c["titles"] for c in categories), default=1)

    recent = db.query_all(f"SELECT {BOOK_COLUMNS} FROM book "
                          "ORDER BY created_at DESC, book_id DESC LIMIT 5")
    attention = db.query_all(f"SELECT {BOOK_COLUMNS} FROM book WHERE quantity <= %s "
                             "ORDER BY quantity ASC, title ASC LIMIT 5", (low,))

    return render_template("dashboard.html", stats=stats, categories=categories,
                           max_titles=max_titles, recent=recent, attention=attention)


# --------------------------------------------------------------------------
# READ: list, search, filter, paginate
# --------------------------------------------------------------------------
@books_bp.route("/books")
@login_required
def list_books():
    q = " ".join(request.args.get("q", "").split())[:100]
    category = request.args.get("category", "").strip()
    sort = request.args.get("sort", "title")
    if sort not in SORT_OPTIONS:
        sort = "title"
    page = request.args.get("page", 1, type=int) or 1
    per_page = current_app.config["BOOKS_PER_PAGE"]

    where, params = [], []
    if q:
        like = f"%{escape_like(q)}%"
        isbn_like = f"%{escape_like(normalize_isbn(q) or q)}%"
        where.append("(title LIKE %s OR author LIKE %s OR isbn LIKE %s OR category LIKE %s)")
        params += [like, like, isbn_like, like]
    if category:
        where.append("category = %s")
        params.append(category)
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    total = db.query_scalar(f"SELECT COUNT(*) FROM book {where_sql}", tuple(params))
    pages = max(1, math.ceil(total / per_page))
    page = min(max(page, 1), pages)

    books = db.query_all(
        f"SELECT {BOOK_COLUMNS} FROM book {where_sql} "
        f"ORDER BY {SORT_OPTIONS[sort][1]} LIMIT %s OFFSET %s",
        tuple(params) + (per_page, (page - 1) * per_page),
    )

    return render_template(
        "books.html", books=books, q=q, category=category, sort=sort,
        sort_options=SORT_OPTIONS, categories=all_categories(),
        page=page, pages=pages, total=total, per_page=per_page,
        first_item=(page - 1) * per_page + 1 if total else 0,
        last_item=min(page * per_page, total),
    )


@books_bp.route("/books/<int:book_id>")
@login_required
def book_details(book_id):
    book = get_book_or_404(book_id)
    return render_template("book_details.html", book=book)


# --------------------------------------------------------------------------
# CREATE
# --------------------------------------------------------------------------
@books_bp.route("/books/add", methods=["GET", "POST"])
@login_required
def add_book():
    form, errors = {"quantity": "1"}, {}

    if request.method == "POST":
        form = request.form
        data, errors = validate_book(request.form, current_app.config["MAX_QUANTITY"])

        if "isbn" not in errors and isbn_taken(data["isbn"]):
            errors["isbn"] = "A book with this ISBN already exists in the catalogue."

        if not errors:
            data["category"] = canonical_category(data["category"])
            try:
                new_id, _ = db.execute(
                    "INSERT INTO book (title, author, isbn, category, publisher, "
                    "publication_year, quantity, shelf_location) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                    book_params(data),
                )
            except mysql.connector.DatabaseError as exc:
                errors = database_rule_errors(exc)
            else:
                flash(f'"{data["title"]}" was added to the catalogue successfully.', "success")
                return redirect(url_for("books.book_details", book_id=new_id))

        flash("The book was not saved. Please correct the highlighted fields.", "error")

    return render_template("add_book.html", form=form, errors=errors,
                           categories=all_categories()), (422 if errors else 200)


# --------------------------------------------------------------------------
# UPDATE
# --------------------------------------------------------------------------
@books_bp.route("/books/<int:book_id>/edit", methods=["GET", "POST"])
@login_required
def edit_book(book_id):
    book = get_book_or_404(book_id)
    form, errors = book_to_form(book), {}

    if request.method == "POST":
        form = request.form
        data, errors = validate_book(request.form, current_app.config["MAX_QUANTITY"])

        if "isbn" not in errors and isbn_taken(data["isbn"], exclude_id=book_id):
            errors["isbn"] = "Another book in the catalogue already uses this ISBN."

        if not errors:
            data["category"] = canonical_category(data["category"])
            try:
                db.execute(
                    "UPDATE book SET title = %s, author = %s, isbn = %s, category = %s, "
                    "publisher = %s, publication_year = %s, quantity = %s, shelf_location = %s "
                    "WHERE book_id = %s",
                    book_params(data) + (book_id,),
                )
            except mysql.connector.DatabaseError as exc:
                errors = database_rule_errors(exc)
            else:
                flash(f'Changes to "{data["title"]}" were saved successfully.', "success")
                return redirect(url_for("books.book_details", book_id=book_id))

        flash("Your changes were not saved. Please correct the highlighted fields.", "error")

    return render_template("edit_book.html", book=book, form=form, errors=errors,
                           categories=all_categories()), (422 if errors else 200)


@books_bp.post("/books/<int:book_id>/quantity")
@login_required
def adjust_quantity(book_id):
    """Quick stock update from the details page: add, remove or set copies."""
    book = get_book_or_404(book_id)
    back = redirect(url_for("books.book_details", book_id=book_id))
    max_qty = current_app.config["MAX_QUANTITY"]
    action = request.form.get("action")
    raw = request.form.get("amount", "").strip()

    if action not in ("add", "remove", "set"):
        flash("Unknown stock action.", "error")
        return back
    if raw.startswith("-"):
        flash("Quantities cannot be negative.", "error")
        return back
    if not raw.isdigit():
        flash("Enter a whole number of copies.", "error")
        return back
    amount = int(raw)
    if action in ("add", "remove") and amount < 1:
        flash("Enter at least 1 copy to add or remove.", "warning")
        return back

    if action == "add":
        _, changed = db.execute(
            "UPDATE book SET quantity = quantity + %s WHERE book_id = %s AND quantity + %s <= %s",
            (amount, book_id, amount, max_qty))
        if not changed:
            flash(f"Cannot add {amount} copies: the limit is {max_qty:,} per title.", "error")
            return back
    elif action == "remove":
        # The WHERE clause makes this atomic: stock can never go below zero,
        # even if two people remove copies at the same moment.
        _, changed = db.execute(
            "UPDATE book SET quantity = quantity - %s WHERE book_id = %s AND quantity >= %s",
            (amount, book_id, amount))
        if not changed:
            flash(f"Cannot remove {amount} copies: only {book['quantity']} available. "
                  "Quantity cannot go below zero.", "error")
            return back
    else:
        if amount > max_qty:
            flash(f"Quantity cannot be more than {max_qty:,}.", "error")
            return back
        db.execute("UPDATE book SET quantity = %s WHERE book_id = %s", (amount, book_id))

    new_qty = db.query_scalar("SELECT quantity FROM book WHERE book_id = %s", (book_id,))
    flash(f'Stock updated: "{book["title"]}" now has {new_qty} '
          f'{"copy" if new_qty == 1 else "copies"}.', "success")
    return back


# --------------------------------------------------------------------------
# DELETE (administrators only)
# --------------------------------------------------------------------------
@books_bp.route("/books/<int:book_id>/delete", methods=["GET", "POST"])
@admin_required
def delete_book(book_id):
    book = get_book_or_404(book_id)

    if request.method == "POST":
        if request.form.get("confirm") != "yes":
            flash("Tick the confirmation box to delete this book.", "warning")
            return render_template("delete_confirm.html", book=book)
        db.execute("DELETE FROM book WHERE book_id = %s", (book_id,))
        flash(f'"{book["title"]}" was permanently deleted from the catalogue.', "success")
        return redirect(url_for("books.list_books"))

    # GET: a confirmation page (used when JavaScript is off; with JavaScript a
    # confirmation dialog opens instead and posts straight to this URL).
    return render_template("delete_confirm.html", book=book)


# --------------------------------------------------------------------------
# JSON helper for live form validation
# --------------------------------------------------------------------------
@books_bp.route("/api/isbn-check")
@login_required
def api_isbn_check():
    isbn = normalize_isbn(request.args.get("isbn", ""))
    exclude = request.args.get("exclude", type=int)
    valid = is_valid_isbn(isbn)
    available = valid and not isbn_taken(isbn, exclude_id=exclude)
    return jsonify(isbn=isbn, valid=valid, available=available)
