import os
import sqlite3
from contextlib import closing
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import connection
from django.utils import timezone


def save_form(form):
    instance = form.save(commit=False)
    instance.save()
    return instance


def backup_database(destination=None):
    """Read the live SQLite connection, including committed WAL transactions."""
    directory = Path(destination or settings.DATA_DIR / "backups")
    directory.mkdir(parents=True, exist_ok=True)
    stamp = timezone.localtime().strftime("%Y%m%d-%H%M%S-%f")
    target = directory / f"db-{stamp}.sqlite3"
    partial = target.with_suffix(".partial")
    connection.ensure_connection()
    if connection.in_atomic_block:
        raise ValidationError("پشتیبان‌گیری باید خارج از تراکنش نوشتن اجرا شود.")
    try:
        # Exclusive creation prevents overwriting any existing backup.
        fd = os.open(partial, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.close(fd)
        with closing(sqlite3.connect(partial)) as backup:
            connection.connection.backup(backup)
            if backup.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
                raise ValidationError("بررسی سلامت پشتیبان ناموفق بود.")
        os.replace(partial, target)
    except Exception:
        partial.unlink(missing_ok=True)
        raise
    return target
