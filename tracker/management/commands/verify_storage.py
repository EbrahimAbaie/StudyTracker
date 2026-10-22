from django.core.management.base import BaseCommand, CommandError
from django.db import connection


class Command(BaseCommand):
    help = "Verify SQLite WAL, NORMAL synchronous mode and 20 second busy timeout."

    def handle(self, *args, **options):
        with connection.cursor() as cursor:
            actual = {
                name: cursor.execute(f"PRAGMA {name}").fetchone()[0]
                for name in ("journal_mode", "synchronous", "busy_timeout")
            }
        if actual != {"journal_mode": "wal", "synchronous": 1, "busy_timeout": 20000}:
            raise CommandError(f"Unexpected SQLite settings: {actual}")
        self.stdout.write(self.style.SUCCESS(f"SQLite verified: {actual}"))
