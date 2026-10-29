"""Test-only settings: run the suite without MySQL/XAMPP.

Usage:
    python manage.py test --settings=mysite.settings_sqlite

The application itself keeps using MySQL (``mysite.settings``). This module
only swaps the database for an in-memory SQLite file so verification never
needs a running database server.
"""

import os

from .settings import *  # noqa: F401,F403

# Defaults to in-memory (fast, isolated). Set SQLITE_NAME to a file path when
# you need a persistent scratch database for a manual render check.
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.environ.get('SQLITE_NAME', ':memory:'),
    }
}
