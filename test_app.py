"""End-to-end test of every route against the real MySQL database.

Run from this folder:  python test_app.py
It adds one temporary book, exercises create/read/update/delete and the
validation rules, then deletes that book again -- your data is left as it was.
"""
import os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app import app

app.config["TESTING"] = False
results = []
def check(name, cond):
    results.append((name, bool(cond)))
    print(("PASS " if cond else "FAIL ") + name)

def token(html):
    m = re.search(r'name="csrf_token" value="([^"]+)"', html)
    return m.group(1) if m else None

def login(c, user, pw):
    t = token(c.get("/login").get_data(as_text=True))
    return c.post("/login", data={"username": user, "password": pw, "csrf_token": t}, follow_redirects=True)

TEST_ISBN = "9780596007126"   # valid ISBN-13 (Head First Design Patterns)
TEST_ISBN2 = "0-306-40615-2"  # valid ISBN-10

# Read the current totals so the checks still hold after you add or edit books.
import db
with app.app_context():
    TITLES, COPIES, CATS = db.query_one(
        "SELECT COUNT(*) AS t, COALESCE(SUM(quantity), 0) AS c, COUNT(DISTINCT category) AS k FROM book"
    ).values()
    TITLES, COPIES, CATS = int(TITLES), int(COPIES), int(CATS)
PER_PAGE = app.config["BOOKS_PER_PAGE"]
LAST_PAGE = max(1, -(-TITLES // PER_PAGE))
LAST_ROWS = TITLES - (LAST_PAGE - 1) * PER_PAGE
print(f"Catalogue now: {TITLES} titles, {COPIES} copies, {CATS} categories")

with app.test_client() as c:
    # --- auth ---
    r = c.get("/")
    check("unauthenticated dashboard redirects to login", r.status_code == 302 and "/login" in r.location)
    r = login(c, "admin", "wrong")
    check("wrong password rejected", r.status_code == 401 and "Invalid username or password" in r.get_data(as_text=True))
    r = c.post("/login", data={"username": "admin", "password": "admin123"})
    check("POST without CSRF token rejected", r.status_code == 400)
    r = login(c, "admin", "admin123")
    html = r.get_data(as_text=True)
    check("admin login works -> dashboard", r.status_code == 200 and "Welcome back" in html and "Total copies" in html)
    check(f"dashboard shows {TITLES} titles", f">{TITLES:,}<" in html)
    check(f"dashboard shows {COPIES} copies", f">{COPIES:,}<" in html)
    check(f"dashboard shows {CATS} categories", f">{CATS}<" in html)

    # --- read ---
    r = c.get("/books"); html = r.get_data(as_text=True)
    check("list page 1 shows a full page", html.count('class="book-title"') == min(PER_PAGE, TITLES) and f"of <strong>{TITLES}</strong>" in html)
    r = c.get(f"/books?page={LAST_PAGE}"); html = r.get_data(as_text=True)
    check(f"last page shows {LAST_ROWS} rows", html.count('class="book-title"') == LAST_ROWS)
    r = c.get("/books?page=99")
    check("out-of-range page clamps", r.status_code == 200 and r.get_data(as_text=True).count('class="book-title"') == LAST_ROWS)
    r = c.get("/books?q=achebe"); html = r.get_data(as_text=True)
    check("search by author", "Things Fall Apart" in html and html.count('class="book-title"') == 1)
    r = c.get("/books?q=978-0-13-235088-4"); html = r.get_data(as_text=True)
    check("search by hyphenated ISBN", "Clean Code" in html and html.count('class="book-title"') == 1)
    r = c.get("/books?q=algorithms"); check("search by title", r.get_data(as_text=True).count('class="book-title"') == 2)
    r = c.get("/books?q=history"); check("search by category/title", r.get_data(as_text=True).count('class="book-title"') >= 2)
    r = c.get("/books?category=Fiction"); html = r.get_data(as_text=True)
    check("filter by category", html.count('class="book-title"') == 4)
    r = c.get("/books?q=%25"); check("LIKE wildcard escaped (search '%')", "No books found" in r.get_data(as_text=True))
    r = c.get("/books?q=' OR 1=1 --"); check("SQL injection text is just a search", r.status_code == 200 and "No books found" in r.get_data(as_text=True))
    r = c.get("/books?sort=quantity;DROP TABLE book"); check("bad sort ignored", r.status_code == 200)
    r = c.get("/books?category=Fiction&page=1&sort=author"); html = r.get_data(as_text=True)
    check("sort by author", html.index("Fitzgerald") < html.index("Orwell") < html.index("Harper Lee") < html.index("Austen"))
    r = c.get("/books/1"); check("details page", r.status_code == 200 and "Clean Code" in r.get_data(as_text=True))
    r = c.get("/books/99999"); check("missing book 404", r.status_code == 404)

    # --- create ---
    t = token(c.get("/books/add").get_data(as_text=True))
    r = c.post("/books/add", data={"csrf_token": t})
    html = r.get_data(as_text=True)
    check("empty add -> required errors", r.status_code == 422 and "Title is required" in html and "ISBN is required" in html and "Shelf location is required" in html)
    bad = {"csrf_token": t, "title": "T", "author": "A", "isbn": "9780596007127", "category": "X",
           "quantity": "-5", "shelf_location": "S", "publication_year": "3000"}
    html = c.post("/books/add", data=bad).get_data(as_text=True)
    check("bad ISBN checksum rejected", "valid ISBN-10 or ISBN-13" in html)
    check("negative quantity rejected", "Quantity cannot be negative" in html)
    check("future year rejected", "Publication year must be between" in html)
    html = c.post("/books/add", data={**bad, "quantity": "2.5"}).get_data(as_text=True)
    check("decimal quantity rejected", "whole number" in html)
    dup = {**bad, "isbn": "978-0-13-235088-4", "quantity": "3", "publication_year": "2001"}
    html = c.post("/books/add", data=dup).get_data(as_text=True)
    check("duplicate ISBN (hyphenated) rejected", "already exists" in html)
    check("form keeps entered values after error", 'value="T"' in html)

    good = {"csrf_token": t, "title": "  Head First   Design Patterns ", "author": "Eric Freeman",
            "isbn": "978-0-596-00712-6", "category": "computer science", "publisher": "",
            "publication_year": "2004", "quantity": "3", "shelf_location": "CS-A3-01"}
    r = c.post("/books/add", data=good)
    check("valid add redirects to details", r.status_code == 302 and "/books/" in r.location)
    new_id = int(r.location.rstrip("/").split("/")[-1])
    html = c.get(r.location).get_data(as_text=True)
    check("success message after add", "added to the catalogue successfully" in html)
    check("whitespace normalised in title", "Head First Design Patterns" in html)
    check("category reuses existing spelling", ">Computer Science<" in html)
    check("ISBN stored normalised", TEST_ISBN in html)
    check("empty publisher shown as Not recorded", "Not recorded" in html)
    r = c.get(f"/api/isbn-check?isbn={TEST_ISBN}"); check("api: new ISBN now taken", r.json == {"isbn": TEST_ISBN, "valid": True, "available": False})
    r = c.get(f"/api/isbn-check?isbn={TEST_ISBN}&exclude={new_id}"); check("api: own ISBN ok when editing", r.json["available"] is True)
    r = c.get("/api/isbn-check?isbn=123"); check("api: invalid ISBN", r.json["valid"] is False)

    # --- update ---
    html = c.get(f"/books/{new_id}/edit").get_data(as_text=True)
    check("edit form pre-filled", 'value="Head First Design Patterns"' in html and 'value="CS-A3-01"' in html and 'value="3"' in html and 'value="2004"' in html)
    upd = {**good, "title": "Head First Design Patterns (2nd Ed.)", "isbn": TEST_ISBN2, "quantity": "12",
           "publisher": "O'Reilly <Media>", "publication_year": ""}
    r = c.post(f"/books/{new_id}/edit", data=upd, follow_redirects=True); html = r.get_data(as_text=True)
    check("update saved with confirmation", "were saved successfully" in html and "(2nd Ed.)" in html)
    check("ISBN-10 accepted", "0306406152" in html)
    check("HTML in input is escaped (XSS safe)", "O&#39;Reilly &lt;Media&gt;" in html)
    r = c.post(f"/books/{new_id}/edit", data={**upd, "isbn": "9780132350884"})
    check("edit to another book's ISBN rejected", r.status_code == 422 and "Another book" in r.get_data(as_text=True))
    r = c.post(f"/books/{new_id}/edit", data={**upd, "quantity": "-1"})
    check("edit negative quantity rejected", r.status_code == 422)

    # --- stock adjustments ---
    def adj(action, amount):
        return c.post(f"/books/{new_id}/quantity", data={"csrf_token": t, "action": action, "amount": amount},
                      follow_redirects=True).get_data(as_text=True)
    html = adj("add", "5"); check("add copies 12+5=17", "now has 17 copies" in html)
    html = adj("remove", "7"); check("remove copies 17-7=10", "now has 10 copies" in html)
    html = adj("remove", "11"); check("cannot remove below zero", "cannot go below zero" in html)
    html = adj("set", "-3"); check("set negative rejected", "cannot be negative" in html)
    html = adj("set", "0"); check("set to 0", "now has 0 copies" in html and "Out of stock" in html)
    html = adj("set", "1"); check("singular copy wording", "now has 1 copy." in html)
    html = adj("add", "abc"); check("non-numeric amount rejected", "whole number" in html)

    # --- delete permission (librarian role) ---
    with app.test_client() as c2:
        login(c2, "librarian", "library123")
        html = c2.get(f"/books/{new_id}").get_data(as_text=True)
        check("librarian sees no delete button", "data-delete-trigger" not in html)
        t2 = token(c2.get("/books").get_data(as_text=True))
        r = c2.post(f"/books/{new_id}/delete", data={"csrf_token": t2, "confirm": "yes"})
        check("librarian cannot delete (403)", r.status_code == 403)
        r = c2.get("/books/add"); check("librarian can open add form", r.status_code == 200)

    # --- delete ---
    html = c.get(f"/books/{new_id}/delete").get_data(as_text=True)
    check("delete confirm page", "cannot be undone" in html)
    r = c.post(f"/books/{new_id}/delete", data={"csrf_token": t}, follow_redirects=True)
    check("delete without confirm tick refused", "Tick the confirmation box" in r.get_data(as_text=True) and c.get(f"/books/{new_id}").status_code == 200)
    r = c.post(f"/books/{new_id}/delete", data={"csrf_token": "bad", "confirm": "yes"})
    check("delete with bad CSRF refused", r.status_code == 400)
    r = c.post(f"/books/{new_id}/delete", data={"csrf_token": t, "confirm": "yes"}, follow_redirects=True)
    check("delete works with message", "permanently deleted" in r.get_data(as_text=True))
    check("deleted book is gone (404)", c.get(f"/books/{new_id}").status_code == 404)
    check(f"dashboard back to {TITLES} titles", f">{TITLES:,}<" in c.get("/").get_data(as_text=True))

    # --- every page renders for both themes of layout ---
    for url in ["/", "/books", "/books/add", "/books/1", "/books/1/edit", "/books/1/delete", "/nope"]:
        r = c.get(url)
        check(f"GET {url} -> {r.status_code}", r.status_code in (200, 404))

    # --- logout ---
    r = c.post("/logout", data={"csrf_token": token(c.get("/").get_data(as_text=True))}, follow_redirects=True)
    check("logout", "signed out" in r.get_data(as_text=True) and c.get("/").status_code == 302)
    r = c.get("/static/css/style.css"); check("css served", r.status_code == 200); r.close()
    r = c.get("/static/js/script.js"); check("js served", r.status_code == 200); r.close()

failed = [n for n, ok in results if not ok]
print(f"\n{len(results) - len(failed)}/{len(results)} passed")
sys.exit(1 if failed else 0)
