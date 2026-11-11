"""
Database layer.

* Keeps one mysql-connector connection pool per Flask app.
* Hands each request a single pooled connection (stored on ``flask.g``)
  and returns it to the pool when the request ends.
* Exposes small helpers (query_all / query_one / execute) that ALWAYS use
  parameterised queries -- values are passed separately from the SQL text,
  so user input can never change the structure of a statement.
* Provides the ``flask init-db`` command that runs database.sql.
"""
import os
import re

import click
import mysql.connector
from mysql.connector import pooling
from flask import current_app, g

SQL_SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "database.sql")

# MariaDB (XAMPP) does not know MySQL 8's default collation, so we pin one
# that both servers support.
CHARSET = "utf8mb4"
COLLATION = "utf8mb4_unicode_ci"


class DatabaseUnavailable(Exception):
    """Raised when we cannot obtain a connection to MySQL."""

    def __init__(self, message, errno=None):
        super().__init__(message)
        self.errno = errno


def _connection_args(include_database=True):
    cfg = current_app.config
    args = {
        "host": cfg["DB_HOST"],
        "port": cfg["DB_PORT"],
        "user": cfg["DB_USER"],
        "password": cfg["DB_PASSWORD"],
        "charset": CHARSET,
        "collation": COLLATION,
        "connection_timeout": cfg["DB_CONNECT_TIMEOUT"],
        "use_pure": True,
    }
    if include_database:
        args["database"] = cfg["DB_NAME"]
    return args


def _get_pool():
    """Create the pool lazily so the app can start even if MySQL is down."""
    pool = current_app.extensions.get("library_db_pool")
    if pool is None:
        pool = pooling.MySQLConnectionPool(
            pool_name="library_pool",
            pool_size=current_app.config["DB_POOL_SIZE"],
            pool_reset_session=True,
            autocommit=False,
            **_connection_args(),
        )
        current_app.extensions["library_db_pool"] = pool
    return pool


def get_db():
    """Return the connection for the current request, opening it if needed."""
    if "db" not in g:
        try:
            conn = _get_pool().get_connection()
            conn.ping(reconnect=True, attempts=2, delay=0)
            g.db = conn
        except mysql.connector.Error as exc:
            current_app.logger.error("Database connection failed: %s", exc)
            # A broken pool (e.g. server restarted) is rebuilt next time.
            current_app.extensions.pop("library_db_pool", None)
            raise DatabaseUnavailable(str(exc), getattr(exc, "errno", None)) from exc
    return g.db


def close_db(_exc=None):
    conn = g.pop("db", None)
    if conn is not None:
        try:
            conn.close()  # returns the connection to the pool
        except mysql.connector.Error:
            pass


# --------------------------------------------------------------------------
# Query helpers -- every one of them takes SQL with %s placeholders and a
# separate tuple of parameters.
# --------------------------------------------------------------------------
def query_all(sql, params=()):
    cur = get_db().cursor(dictionary=True)
    try:
        cur.execute(sql, params)
        return cur.fetchall()
    finally:
        cur.close()


def query_one(sql, params=()):
    cur = get_db().cursor(dictionary=True)
    try:
        cur.execute(sql, params)
        return cur.fetchone()
    finally:
        cur.close()


def query_scalar(sql, params=()):
    cur = get_db().cursor()
    try:
        cur.execute(sql, params)
        row = cur.fetchone()
        return row[0] if row else None
    finally:
        cur.close()


def execute(sql, params=()):
    """Run an INSERT/UPDATE/DELETE inside a transaction.

    Returns (lastrowid, rowcount). Rolls back and re-raises on any error.
    """
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute(sql, params)
        conn.commit()
        return cur.lastrowid, cur.rowcount
    except mysql.connector.Error:
        conn.rollback()
        raise
    finally:
        cur.close()


# --------------------------------------------------------------------------
# Schema installation
# --------------------------------------------------------------------------
def split_sql_script(text):
    """Split a .sql file into individual statements.

    Handles ``--`` comment lines and statements spread across several lines.
    (Our script never puts a semicolon at the end of a line inside a string.)
    """
    statements, current = [], []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("--"):
            continue
        current.append(line)
        if stripped.endswith(";"):
            statements.append("\n".join(current).rstrip().rstrip(";"))
            current = []
    if current:
        statements.append("\n".join(current))
    return statements


def run_schema_script(reset=False):
    db_name = current_app.config["DB_NAME"]
    if not re.fullmatch(r"\w+", db_name):
        raise click.ClickException("DB_NAME may only contain letters, digits and underscores.")

    with open(SQL_SCRIPT, encoding="utf-8") as fh:
        script = fh.read().replace("library_db", db_name)

    conn = mysql.connector.connect(**_connection_args(include_database=False))
    cur = conn.cursor()
    try:
        if reset:
            cur.execute(f"CREATE DATABASE IF NOT EXISTS `{db_name}` "
                        f"CHARACTER SET {CHARSET} COLLATE {COLLATION}")
            cur.execute(f"USE `{db_name}`")
            cur.execute("DROP TABLE IF EXISTS book, librarian")
        for statement in split_sql_script(script):
            cur.execute(statement)
            if cur.with_rows:
                cur.fetchall()
        conn.commit()
    finally:
        cur.close()
        conn.close()


@click.command("init-db")
@click.option("--reset", is_flag=True,
              help="Drop the existing tables first and reload the sample data.")
def init_db_command(reset):
    """Create the database, tables, sample books and default librarians."""
    if reset:
        click.confirm("This deletes ALL books and librarian accounts. Continue?", abort=True)
    try:
        run_schema_script(reset=reset)
    except mysql.connector.Error as exc:
        raise click.ClickException(f"Could not set up the database: {exc}")
    click.secho(f"Database '{current_app.config['DB_NAME']}' is ready.", fg="green")


def init_app(app):
    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)
