"""Settings for running the test suite without PostgreSQL: manage.py test --settings=backend.test_settings"""
from .settings import *  # noqa: F401,F403

DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
