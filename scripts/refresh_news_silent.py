"""Windowless refresh runner for Windows Task Scheduler.

Runs under ``pythonw.exe`` (no console flash) and appends Django's output to
``%TEMP%\\hermes-refresh.log``.
"""

import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)
os.chdir(BASE_DIR)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mysite.settings")

log_path = os.path.join(os.environ.get("TEMP", BASE_DIR), "hermes-refresh.log")
with open(log_path, "a", encoding="utf-8") as log:
    sys.stdout = sys.stderr = log
    import django

    django.setup()
    from django.core.management import call_command

    print("[silent] refresh start")
    try:
        call_command("refresh_news", limit=25)
    except Exception as exc:  # keep the task exit code meaningful
        print("[silent] refresh failed:", repr(exc))
        raise
    finally:
        sys.stdout.flush()
