"""
Server-side validation for book records.

The browser also validates (static/js/script.js), but client-side checks can
be bypassed, so every submission is validated again here before it reaches
the database. The database itself is the last line of defence (UNIQUE and
CHECK constraints in database.sql).
"""
import re
from datetime import date

# field name -> (label, max length, required?)
BOOK_FIELDS = {
    "title":            ("Title", 255, True),
    "author":           ("Author", 255, True),
    "isbn":             ("ISBN", 20, True),
    "category":         ("Category", 100, True),
    "publisher":        ("Publisher", 255, False),
    "publication_year": ("Publication year", 4, False),
    "quantity":         ("Quantity", 6, True),
    "shelf_location":   ("Shelf location", 100, True),
}

MIN_YEAR = 1000
MAX_QUANTITY_DEFAULT = 100000


def normalize_isbn(raw):
    """Remove spaces and hyphens: '978-0-13-235088-4' -> '9780132350884'."""
    return re.sub(r"[\s\-]", "", raw or "").upper()


def is_valid_isbn(isbn):
    """True if ``isbn`` (already normalised) is a valid ISBN-10 or ISBN-13."""
    if re.fullmatch(r"\d{9}[\dX]", isbn):
        total = sum((10 - i) * (10 if ch == "X" else int(ch)) for i, ch in enumerate(isbn))
        return total % 11 == 0
    if re.fullmatch(r"\d{13}", isbn):
        total = sum(int(ch) * (1 if i % 2 == 0 else 3) for i, ch in enumerate(isbn))
        return total % 10 == 0
    return False


def _clean_text(value):
    # Trim and collapse runs of whitespace ("  Clean   Code " -> "Clean Code").
    return " ".join((value or "").split())


def validate_book(form, max_quantity=MAX_QUANTITY_DEFAULT):
    """Validate submitted book data.

    Returns ``(data, errors)`` where ``data`` holds cleaned, correctly typed
    values ready for SQL and ``errors`` maps field names to messages.
    """
    data, errors = {}, {}

    for field, (label, max_len, required) in BOOK_FIELDS.items():
        value = _clean_text(form.get(field))
        if required and not value:
            errors[field] = f"{label} is required."
        elif len(value) > max_len and field not in ("publication_year", "quantity"):
            errors[field] = f"{label} must be at most {max_len} characters."
        data[field] = value

    # ISBN: format + checksum
    if "isbn" not in errors:
        isbn = normalize_isbn(data["isbn"])
        data["isbn"] = isbn
        if not is_valid_isbn(isbn):
            errors["isbn"] = ("Enter a valid ISBN-10 or ISBN-13 (digits only; hyphens "
                              "and spaces are allowed). Check the last digit.")

    # Publication year: optional, whole number, not in the future
    year_raw = data["publication_year"]
    current_year = date.today().year
    if not year_raw:
        data["publication_year"] = None
    elif not re.fullmatch(r"\d{4}", year_raw):
        errors["publication_year"] = "Publication year must be a 4-digit year, e.g. 2019."
    else:
        year = int(year_raw)
        if not MIN_YEAR <= year <= current_year:
            errors["publication_year"] = (f"Publication year must be between {MIN_YEAR} "
                                          f"and {current_year}.")
        data["publication_year"] = year

    # Quantity: required, whole number, never negative
    if "quantity" not in errors:
        qty_raw = data["quantity"]
        if re.fullmatch(r"-\d+", qty_raw):
            errors["quantity"] = "Quantity cannot be negative."
        elif not re.fullmatch(r"\d+", qty_raw):
            errors["quantity"] = "Quantity must be a whole number (0 or more)."
        else:
            qty = int(qty_raw)
            if qty > max_quantity:
                errors["quantity"] = f"Quantity cannot be more than {max_quantity:,}."
            data["quantity"] = qty

    # Publisher is optional -> store NULL rather than an empty string
    if not data["publisher"]:
        data["publisher"] = None

    return data, errors
