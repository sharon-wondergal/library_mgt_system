"""
Export a static "design preview" of the system.

The files in templates/ are Flask/Jinja templates: they contain placeholders
like {{ url_for(...) }} that only become real pages when Flask runs. Opened
directly they look like plain, unstyled text.

This script renders each page through the real app (with data from MySQL)
and saves finished HTML files into design_preview/. Those files open with a
double-click in any browser -- no Python or MySQL needed -- which makes them
handy for showing or sharing the design.

Run from this folder (MySQL must be running):
    python export_preview.py
"""
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from app import app  # noqa: E402

OUT = os.path.join(HERE, "design_preview")

# (output file, URL to render, description shown on the index page)
PAGES = [
    ("login.html",          "/login",          "Sign-in page"),
    ("dashboard.html",      "/",               "Dashboard with statistics"),
    ("books.html",          "/books",          "All books: table, search, filter, pagination"),
    ("books_page2.html",    "/books?page=2",   "All books, page 2"),
    ("books_search.html",   "/books?q=african", "Search results (\"african\")"),
    ("book_details.html",   "/books/1",        "Book details + stock update"),
    ("add_book.html",       "/books/add",      "Add new book form"),
    ("add_book_errors.html", None,             "Add form showing validation errors"),
    ("edit_book.html",      "/books/1/edit",   "Edit book form (pre-filled)"),
    ("delete_confirm.html", "/books/1/delete", "Delete confirmation"),
    ("error_404.html",      "/no-such-page",   "Error page (404)"),
]

BANNER = ('<div style="position:fixed;bottom:12px;right:12px;z-index:200;background:#0f1f3d;'
          'color:#fff;font:600 12px/1.4 Segoe UI,Arial,sans-serif;padding:8px 12px;border-radius:8px;'
          'box-shadow:0 4px 14px rgba(0,0,0,.25)">Design preview &middot; not connected to the '
          'database &middot; <a href="index.html" style="color:#f1d98a">all pages</a></div>')


def link_target(path):
    """Map an app URL to the matching preview file (or '#')."""
    path = path.replace("&amp;", "&")
    if path.startswith("/static/"):
        return path[1:]
    if path in ("/", "/login") or path.startswith("/login?"):
        return "dashboard.html" if path == "/" else "login.html"
    if re.fullmatch(r"/books/\d+/edit", path):
        return "edit_book.html"
    if re.fullmatch(r"/books/\d+/delete", path):
        return "delete_confirm.html"
    if re.fullmatch(r"/books/\d+", path):
        return "book_details.html"
    if path.startswith("/books/add"):
        return "add_book.html"
    if path.startswith("/books?page=2") or "page=2" in path:
        return "books_page2.html"
    if path.startswith("/books"):
        return "books.html"
    return "#"


def make_static(html):
    html = re.sub(r'(href|src)="(/[^"]*)"', lambda m: f'{m.group(1)}="{link_target(m.group(2))}"', html)
    html = re.sub(r'action="(/[^"]*)"', lambda m: f'action="{link_target(m.group(1))}"', html)
    html = re.sub(r'<form method="post"( action="[^"]*")?', '<form method="get" action="#"', html)
    html = re.sub(r'name="csrf_token" value="[^"]*"', 'name="csrf_token" value=""', html)
    html = re.sub(r'(<body[^>]*>)', r'\1' + BANNER, html, count=1)
    return html


def csrf(html):
    m = re.search(r'name="csrf_token" value="([^"]+)"', html)
    return m.group(1) if m else ""


def main():
    # Render everything first; the old preview is only replaced once all
    # pages rendered successfully, so a failure never leaves you with nothing.
    with app.test_client() as client:
        pages = {}
        pages["login.html"] = client.get("/login").get_data(as_text=True)

        token = csrf(pages["login.html"])
        r = client.post("/login", data={"username": "admin", "password": "admin123",
                                        "csrf_token": token})
        if r.status_code != 302:
            sys.exit("Could not sign in as admin/admin123 -- is MySQL running and the "
                     "database set up (flask init-db)?")

        for filename, url, _ in PAGES:
            if url and filename != "login.html":
                pages[filename] = client.get(url).get_data(as_text=True)

        # A form submitted empty, to show the validation messages.
        token = csrf(pages["add_book.html"])
        pages["add_book_errors.html"] = client.post(
            "/books/add", data={"csrf_token": token, "isbn": "12345", "quantity": "-3"}
        ).get_data(as_text=True)

    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    shutil.copytree(os.path.join(HERE, "static"), os.path.join(OUT, "static"))
    for filename, html in pages.items():
        with open(os.path.join(OUT, filename), "w", encoding="utf-8") as fh:
            fh.write(make_static(html))

    items = "\n".join(
        f'<li><a href="{f}">{desc}</a> <span>{f}</span></li>' for f, _, desc in PAGES)
    index = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Design preview · Campus Library</title>
<link rel="stylesheet" href="static/css/style.css">
<style>
  .preview-list {{ list-style: none; padding: 0; margin: 0; }}
  .preview-list li {{ padding: .7rem 0; border-top: 1px solid var(--grey-100); display: flex;
                      justify-content: space-between; gap: 1rem; flex-wrap: wrap; }}
  .preview-list li:first-child {{ border-top: 0; }}
  .preview-list a {{ font-weight: 600; }}
  .preview-list span {{ color: var(--grey-500); font-family: var(--mono); font-size: .8rem; }}
</style></head>
<body class="layout-plain"><div class="main"><main class="content">
<section class="auth-card" style="max-width:640px;margin:2rem auto">
  <div class="auth-brand">
    <img src="static/images/logo.svg" alt="" width="56" height="56">
    <h1>Campus Library</h1>
    <p>Design preview: every screen of the Library Book Management System</p>
  </div>
  <ul class="preview-list">{items}</ul>
  <p class="auth-hint">These are saved snapshots for viewing the design. Buttons and forms do
    not save anything here. To use the real system, run <code>python app.py</code>.</p>
</section></main></div></body></html>"""
    with open(os.path.join(OUT, "index.html"), "w", encoding="utf-8") as fh:
        fh.write(index)

    print(f"Design preview written to {OUT}")
    print("Open design_preview/index.html in your browser.")


if __name__ == "__main__":
    main()
