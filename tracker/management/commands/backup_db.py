from django.core.management.base import BaseCommand, CommandError

from tracker.services import backup_database


class Command(BaseCommand):
    help = "Create an integrity-checked, live SQLite backup in data/backups."

    def handle(self, *args, **options):
        try:
            path = backup_database()
        except Exception as exc:
            raise CommandError(f"Backup failed: {exc}") from exc
        self.stdout.write(self.style.SUCCESS(str(path)))
