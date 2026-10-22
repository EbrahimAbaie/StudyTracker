from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from tracker.models import (
    ExamSettings,
    PracticeSession,
    StudyResource,
    StudySession,
    Subject,
)


class Command(BaseCommand):
    help = "Add an optional demo once; never runs at startup or modifies existing subjects."

    @transaction.atomic
    def handle(self, *args, **options):
        names = ["ساختمان داده", "سیستم عامل", "پایگاه داده"]
        existing = set(
            Subject.objects.filter(name__in=names).values_list("name", flat=True)
        )
        if existing == set(names):
            self.stdout.write("Demo subjects already exist; nothing changed.")
            return
        if existing:
            raise CommandError(
                "Some demo subject names already exist. Existing data was preserved; use an empty database for the demo."
            )
        today = timezone.localdate()
        if not ExamSettings.objects.exists():
            ExamSettings.objects.create(
                title="کنکور ارشد مهندسی کامپیوتر — نمونه",
                exam_date=today + timedelta(days=148),
                weekly_available_minutes=1800,
            )
        for index, name in enumerate(names, start=1):
            subject = Subject.objects.create(
                name=name,
                order=index,
                practice_target_minutes=1800,
                practice_target_questions=2000,
            )
            theory = StudyResource.objects.create(
                subject=subject, title="دوره اصلی", planned_minutes=2400
            )
            StudyResource.objects.create(
                subject=subject,
                title="نکته و تست",
                resource_type=StudyResource.Type.TIPS_TEST,
                planned_minutes=1200,
            )
            for offset in (13, 10, 7, 4, 1, 0):
                StudySession.objects.create(
                    resource=theory,
                    date=today - timedelta(days=offset),
                    duration_minutes=100 + (index - 1) * 20,
                )
                PracticeSession.objects.create(
                    subject=subject,
                    date=today - timedelta(days=offset),
                    duration_minutes=50,
                    correct_count=29,
                    wrong_count=8,
                    unanswered_count=3,
                )
        self.stdout.write(
            self.style.SUCCESS(
                "Demo data created. Run backup_db before making real changes."
            )
        )
