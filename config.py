"""
Application configuration.

Every value can be overridden with an environment variable, so you never
have to edit code to point the app at a different MySQL server.

    Windows (PowerShell):  $env:DB_PASSWORD = "secret"
    macOS / Linux:         export DB_PASSWORD=secret
"""
import os
from datetime import timedelta


class Config:
    # Used to sign the session cookie. Change it for any real deployment.
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-change-this-secret-key")

    # --- MySQL connection -------------------------------------------------
    DB_HOST = os.environ.get("DB_HOST", "localhost")
    DB_PORT = int(os.environ.get("DB_PORT", "3306"))
    DB_USER = os.environ.get("DB_USER", "root")
    DB_PASSWORD = os.environ.get("DB_PASSWORD", "")
    DB_NAME = os.environ.get("DB_NAME", "library_db")
    DB_POOL_SIZE = int(os.environ.get("DB_POOL_SIZE", "5"))
    DB_CONNECT_TIMEOUT = 5  # seconds

    # --- Application behaviour -------------------------------------------
    BOOKS_PER_PAGE = 10
    MAX_QUANTITY = 100000          # sanity upper limit for copies of one title
    LOW_STOCK_THRESHOLD = 2        # "low stock" badge at or below this number

    # --- Session security ------------------------------------------------
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)
