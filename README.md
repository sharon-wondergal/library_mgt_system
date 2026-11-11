# Campus Library: Book Management System

A web application that lets librarians manage a school or college library catalogue:
**add, view, search, update and delete books**. It is built with Python Flask,
MySQL and plain HTML, CSS and JavaScript.

**Live design preview:** https://sharon-wondergal.github.io/library_mgt_system/
(saved snapshots of every screen; to use the working system, run it locally as described below)

---

## 1. Features

| Area | What it does |
|---|---|
| **Sign in** | Librarian accounts with hashed passwords. Two roles: `admin` (full access) and `librarian` (can do everything except delete). |
| **Dashboard** | Total titles, total copies, number of categories, out-of-stock count, books per category, recently added books, low-stock list, quick links. |
| **Add book** (Create) | A form with required-field checks, ISBN-10/13 checksum validation, a live check that the ISBN is not already used, and success and error messages. |
| **View books** (Read) | A table with search by title, author, ISBN or category, a category filter, sorting, pagination (10 per page) and a details page for each book. |
| **Edit book** (Update) | The form opens pre-filled with the current details and shows a confirmation after saving. The details page also has a quick **Add / Remove / Set** stock control. |
| **Delete book** (Delete) | Admins only. A confirmation dialog requires a tick in "I understand…" before the Delete button works. Without JavaScript, a confirmation page does the same job. |
| **Responsive UI** | Navy, white and grey theme. The sidebar becomes a slide-out menu on tablets and phones, and less important table columns hide on small screens. |

---

## 2. Requirements

* **Python 3.9 or newer**
* **MySQL 8.0.16+** or **MariaDB 10.4+**. XAMPP's MySQL works.

---

## 3. Installation and running

All commands are run **inside the `library_management` folder**.

### Step 1: Start MySQL
* **XAMPP:** open the XAMPP Control Panel and click **Start** next to *MySQL*.
* **MySQL Server:** make sure the `MySQL80` service is running.

### Step 2: Install the Python packages
```bash
pip install -r requirements.txt
```
(Optional) Use a virtual environment first: `python -m venv venv`, then
`venv\Scripts\activate` on Windows or `source venv/bin/activate` on macOS and Linux.

### Step 3: Configure the database connection
The defaults in `config.py` match a fresh XAMPP install: host `localhost`, port `3306`,
user `root` and **no password**. If your MySQL has a password, set it as an environment
variable (no code change needed):

```powershell
# Windows PowerShell
$env:DB_PASSWORD = "your_mysql_password"
```
```bash
# macOS / Linux
export DB_PASSWORD=your_mysql_password
```
Other settings you can change the same way: `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_NAME`
and `SECRET_KEY`.

### Step 4: Create the database, tables and sample data
Choose **one** of these:

```bash
flask init-db
```
* or, from the MySQL command line: `mysql -u root -p < database.sql`
* or, in **phpMyAdmin**: *Import* → choose `database.sql` → *Go*

This creates the `library_db` database, the `book` and `librarian` tables, **26 sample
books** in 8 categories, and two demo accounts. It is safe to run again, because it never
deletes anything. To wipe everything and reload the sample data (for example before a
demo), run `flask init-db --reset`.

### Step 5: Run the application
```bash
python app.py
```
Open **http://127.0.0.1:5000** in your browser.

### Demo accounts
| Username | Password | Role |
|---|---|---|
| `admin` | `admin123` | Admin: can add, edit **and delete** |
| `librarian` | `library123` | Librarian: can add and edit, cannot delete |

Add more accounts or change a password with `flask create-librarian`. Change the demo
passwords before using the system for real.

### Step 6 (optional): Run the automated tests
```bash
python test_app.py
```
This runs 69 checks against your real database, covering login, every CRUD operation,
validation, search, pagination, permissions and CSRF protection. It adds one temporary
book and deletes it again, so your data is left unchanged.

### Viewing the design without running anything
The files in `templates/` are **Flask templates**, not finished web pages. They contain
placeholders such as `{{ url_for(...) }}` that Flask replaces while the app runs. Opened
directly, they look like plain, unstyled text. That is normal.

To look at the screens without Python or MySQL, open **`design_preview/index.html`**.
It lists saved snapshots of every page, with the full design. The snapshots don't save
anything. To regenerate them after changing the design, run `python export_preview.py`
(MySQL must be running).

---

## 4. Project structure

```
library_management/
├── app.py              Application factory, CSRF guard, error pages, entry point
├── config.py           Settings (DB connection, page size, limits) via env vars
├── db.py               Connection pool, query helpers, `flask init-db` command
├── auth.py             Login/logout, login_required / admin_required, `flask create-librarian`
├── books.py            Dashboard + all book routes (CRUD, search, stock, ISBN API)
├── validators.py       Server-side validation rules and the ISBN checksum check
├── icons.py            Inline SVG icons (works offline, no CDN)
├── database.sql        Database creation script + sample data
├── requirements.txt    Python dependencies
├── test_app.py         End-to-end tests
├── export_preview.py   Builds design_preview/ (static snapshots of every page)
├── design_preview/     Open index.html to view the design without running the app
├── templates/
│   ├── base.html           Layout: sidebar, top bar, notifications, delete dialog
│   ├── _macros.html        Shared pieces: book form, stock badge, pagination
│   ├── login.html          Sign-in page
│   ├── dashboard.html      Statistics overview
│   ├── books.html          Book list with search/filter/sort/pagination
│   ├── add_book.html       Create form
│   ├── edit_book.html      Update form (pre-filled)
│   ├── book_details.html   Single book + quick stock update
│   ├── delete_confirm.html Delete confirmation page (no-JavaScript fallback)
│   └── error.html          Friendly 400/403/404/500/503 pages
└── static/
    ├── css/style.css       All styling, responsive breakpoints
    ├── js/script.js        Sidebar, alerts, delete dialog, form validation, live ISBN check
    └── images/             Logo and favicon
```

---

## 5. Database design

### `book`
| Field | Type | Rules |
|---|---|---|
| `book_id` | INT | Primary key, auto increment |
| `title` | VARCHAR(255) | Required, cannot be blank |
| `author` | VARCHAR(255) | Required, cannot be blank |
| `isbn` | VARCHAR(20) | Required, **UNIQUE**. Stored without hyphens. |
| `category` | VARCHAR(100) | Required, indexed |
| `publisher` | VARCHAR(255) | Optional |
| `publication_year` | INT | Optional, **CHECK** between 1000 and 2100 |
| `quantity` | INT | Required, default 0, **CHECK quantity >= 0** |
| `shelf_location` | VARCHAR(100) | Required |
| `created_at`, `updated_at` | TIMESTAMP | Filled in automatically. Used for "Recently added" and "Last updated". |

### `librarian`
`librarian_id` (PK), `username` (UNIQUE), `full_name`, `password_hash`
(scrypt hash), `role` (`admin` / `librarian`), `created_at`.

---

## 6. How the main components work

**Request flow.** The browser sends a request. Flask matches it to a route in `books.py`
or `auth.py`. The route checks login with `@login_required`, validates input with
`validators.py`, runs parameterised SQL through `db.py`, and renders a Jinja template.
Each response includes flash messages, which `base.html` shows as success, error,
warning or info notifications.

**`db.py`, the database layer.** It creates a mysql-connector **connection pool** the
first time it is needed, so the app still starts if MySQL is down. Each request borrows
one connection, which is returned automatically at the end of the request. All queries
go through `query_all`, `query_one`, `query_scalar` and `execute`, which pass values
separately from the SQL (`%s` placeholders), so user input cannot change the SQL.
`execute` commits on success and rolls back on failure.

**`validators.py`, the validation rules.** `validate_book()` trims input, checks required
fields and lengths, normalises the ISBN (removes hyphens and spaces) and verifies its
check digit. It also checks that the year is a 4-digit year no later than the current
year and that the quantity is a whole number of 0 or more. It returns cleaned data plus
a dictionary of per-field error messages, which the templates show under each field.

**`books.py`, CRUD.**
* *Create and update:* the route validates, checks ISBN uniqueness (when editing, it
  excludes the book itself), reuses the existing spelling of a category
  ("science" becomes "Science"), then runs the INSERT or UPDATE. If two people save the
  same ISBN at the same moment, the database's UNIQUE constraint still blocks it, and the
  error becomes a friendly message.
* *Read:* the search builds a `WHERE` clause from fixed SQL pieces plus parameters.
  LIKE wildcards in the search text are escaped, so searching for `%` finds a literal
  `%`. The sort order comes from a fixed list of options and never from raw input.
  Pagination uses `LIMIT/OFFSET`, and a page number that is too high is moved back to
  the last page.
* *Stock:* "Remove copies" runs
  `UPDATE … SET quantity = quantity - n WHERE book_id = ? AND quantity >= n`,
  so stock can never go negative, even when two people update it at the same moment.
* *Delete:* `@admin_required`. It requires a POST with a valid CSRF token **and** the
  confirmation checkbox.

**`auth.py`, authentication.** Passwords are checked with werkzeug's
`check_password_hash`. A wrong username and a wrong password give the same message and
take about the same time to answer. After login, the session stores the librarian's ID,
name and role. The `next` redirect only accepts paths on this site.

**`app.py`, security and errors.** Every POST must carry the session's random CSRF
token, which blocks forged form submissions from other sites. Error handlers show
friendly pages, including specific advice when MySQL is not running, the database has not
been created, or the password is wrong.

**`script.js`, the front end.** It opens and closes the sidebar on mobile, fades out
success messages, and runs the delete dialog. Cancel is focused by default, Esc or a
click outside closes it, and Delete stays disabled until the box is ticked. It repeats
the server's validation rules for instant feedback, asks `/api/isbn-check` whether an
ISBN is already in use while you type, and auto-submits the filter dropdowns. The server
validates everything again, because browser checks can be bypassed.

---

## 7. Security summary
* Parameterised SQL everywhere (no string-built values). Sort order comes from a fixed list.
* Validation in both the browser and the server, plus database constraints (UNIQUE, CHECK, NOT NULL).
* Password hashing (scrypt). Session cookies are HttpOnly and SameSite=Lax, and sessions expire after 8 hours.
* CSRF tokens on every form. Logout and delete only work through POST.
* Role-based permission: only admins can delete.
* Jinja escapes all output automatically, which protects against XSS.
* Database errors are handled gracefully and never show raw error details to users.

---

## 8. Troubleshooting
| Problem | Fix |
|---|---|
| "Database unavailable" page | Start MySQL in XAMPP and check `DB_HOST`, `DB_PORT` and `DB_PASSWORD`. |
| "The library database does not exist yet" | Run `flask init-db`. |
| `Access denied for user 'root'` | Set `DB_PASSWORD` (see Step 3). |
| `flask: command not found` | Use `python -m flask init-db`. |
| Port 5000 already in use | `$env:PORT = "5050"` (PowerShell) or `PORT=5050 python app.py`. |
| "Form expired" message | Reload the page. The form's security token belongs to an old session. |
