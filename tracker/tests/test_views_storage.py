import io
import sqlite3
import tempfile
from contextlib import closing
from copy import deepcopy
from datetime import timedelta
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import connection
from django.db.backends.sqlite3.base import DatabaseWrapper
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from tracker.models import (
    ExamSettings,
    PracticeSession,
    StudyResource,
    StudySession,
    Subject,
)
from tracker.selectors import dashboard_data, subject_summaries
from tracker.services import backup_database
from tracker.utils import format_jalali


@override_settings(ALLOWED_HOSTS=["testserver", "localhost", "127.0.0.1"])
class ViewTests(TestCase):
    def setUp(self):
        self.today = timezone.localdate()

    def add_data(self):
        exam = ExamSettings.objects.create(
            title="کنکور ارشد",
            exam_date=self.today + timedelta(days=148),
            weekly_available_minutes=1800,
        )
        subject = Subject.objects.create(
            name="ساختمان داده",
            practice_target_minutes=1800,
            practice_target_questions=2000,
        )
        resource = StudyResource.objects.create(
            subject=subject, title="اصلی", planned_minutes=2400
        )
        second = StudyResource.objects.create(
            subject=subject,
            title="نکته و تست",
            planned_minutes=1200,
            resource_type="TIPS_TEST",
        )
        study = StudySession.objects.create(resource=resource, duration_minutes=140)
        practice = PracticeSession.objects.create(
            subject=subject,
            duration_minutes=70,
            correct_count=29,
            wrong_count=8,
            unanswered_count=3,
        )
        return exam, subject, resource, second, study, practice

    def test_empty_pages(self):
        for path in (
            "/",
            "/subjects/",
            "/subjects/add/",
            "/study/add/",
            "/practice/add/",
            "/history/",
            "/settings/",
            "/health/",
            "/admin/login/",
        ):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 200)
        self.assertContains(self.client.get("/"), "برای شروع اطلاعات کنکور را ثبت کن.")
        self.assertEqual(self.client.get("/health/").content, b"OK")

    def test_exam_only_and_subject_without_sessions(self):
        ExamSettings.objects.create(
            title="کنکور", exam_date=self.today, weekly_available_minutes=1800
        )
        self.assertEqual(self.client.get("/").status_code, 200)
        Subject.objects.create(name="سیستم عامل")
        self.assertEqual(self.client.get("/").status_code, 200)

    def test_priority_orders_dashboard_and_aggregated_resources(self):
        last = Subject.objects.create(name="الف آخر", order=10)
        first = Subject.objects.create(name="ی اول", order=1)
        middle = Subject.objects.create(name="ب میانی", order=2)
        resources = [
            StudyResource.objects.create(
                subject=first, title=title, order=priority, planned_minutes=100
            )
            for title, priority in (("الف آخر", 10), ("ی اول", 1), ("ب میانی", 2))
        ]
        for resource in resources:
            StudySession.objects.create(resource=resource, duration_minutes=20)
        for path in ("/", "/subjects/"):
            response = self.client.get(path)
            self.assertEqual(
                [row["subject"].pk for row in response.context["subjects"]],
                [first.pk, middle.pk, last.pk],
            )
        detail = self.client.get(f"/subjects/{first.pk}/")
        self.assertEqual(
            [item["resource"].pk for item in detail.context["row"]["resources"]],
            [resources[1].pk, resources[2].pk, resources[0].pk],
        )

    def test_acceptance_calculations(self):
        self.add_data()
        data = dashboard_data(self.today)
        row = data["subjects"][0]
        self.assertEqual(
            (
                row["planned"],
                row["actual_study"],
                row["actual_practice"],
                row["remaining"],
            ),
            (5400, 140, 70, 5190),
        )
        self.assertEqual(row["stats"]["total"], 40)
        self.assertAlmostEqual(row["stats"]["accuracy"], 29 / 37 * 100)
        self.assertEqual(data["weekly_activity"], 210)
        self.assertEqual(data["capacity"]["days_remaining"], 148)

    def test_complete_pages_and_routes(self):
        exam, subject, resource, second, study, practice = self.add_data()
        paths = [
            "/",
            "/subjects/",
            f"/subjects/{subject.pk}/",
            f"/subjects/{subject.pk}/edit/",
            f"/subjects/{subject.pk}/delete/",
            f"/subjects/{subject.pk}/resources/add/",
            f"/resources/{resource.pk}/edit/",
            f"/resources/{resource.pk}/delete/",
            f"/study/{study.pk}/edit/",
            f"/study/{study.pk}/delete/",
            f"/practice/{practice.pk}/edit/",
            f"/practice/{practice.pk}/delete/",
            "/history/",
            "/settings/",
        ]
        for path in paths:
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 200)

    def test_manual_completion_updates_dashboard(self):
        exam, subject, resource, second, study, practice = self.add_data()
        StudySession.objects.create(resource=second, duration_minutes=840)
        second.is_completed = True
        second.save()
        row = dashboard_data(self.today)["subjects"][0]
        result = next(
            item for item in row["resources"] if item["resource"].pk == second.pk
        )
        self.assertEqual(
            (
                result["planned"],
                result["actual"],
                result["remaining"],
                result["progress"],
            ),
            (1200, 840, 0, 100),
        )
        self.assertContains(self.client.get(f"/subjects/{subject.pk}/"), "تکمیل شده")

    def test_practice_without_target_and_past_exam(self):
        exam, subject, resource, second, study, practice = self.add_data()
        subject.practice_target_minutes = None
        subject.save()
        exam.exam_date = self.today - timedelta(days=1)
        exam.save()
        response = self.client.get("/")
        self.assertContains(response, "هدف زمانی تعیین نشده")
        self.assertContains(response, "آزمون برگزار شده است")

    def test_post_full_acceptance_flow(self):
        response = self.client.post(
            "/settings/",
            {
                "title": "کنکور ۱۴۰۶",
                "exam_date": "۱۴۰۶/۰۲/۱۸",
                "weekly_hours": "۳۰",
                "weekly_minutes": "۰",
            },
        )
        self.assertEqual(response.status_code, 302)
        response = self.client.post(
            "/subjects/add/",
            {
                "name": "ساختمان داده",
                "target_hours": "۳۰",
                "target_minutes": "۰",
                "practice_target_questions": "۲۰۰۰",
                "order": "۱",
                "is_active": "on",
            },
        )
        self.assertEqual(response.status_code, 302)
        subject = Subject.objects.get()
        for title, hours in (("اصلی", "۴۰"), ("نکته و تست", "۲۰")):
            response = self.client.post(
                f"/subjects/{subject.pk}/resources/add/",
                {
                    "title": title,
                    "resource_type": "THEORY",
                    "planned_hours": hours,
                    "planned_minutes_part": "۰",
                    "order": "۱",
                    "is_active": "on",
                },
            )
            self.assertEqual(response.status_code, 302)
        resource = StudyResource.objects.first()
        response = self.client.post(
            "/study/add/",
            {
                "subject": subject.pk,
                "resource": resource.pk,
                "date": format_jalali(self.today),
                "hours": "۲",
                "minutes": "۲۰",
            },
        )
        self.assertEqual(response.status_code, 302)
        response = self.client.post(
            "/practice/add/",
            {
                "subject": subject.pk,
                "date": format_jalali(self.today),
                "hours": "۱",
                "minutes": "۱۰",
                "correct_count": "۲۹",
                "wrong_count": "۸",
                "unanswered_count": "۳",
            },
        )
        self.assertEqual(response.status_code, 302)
        row = self.client.get("/").context["subjects"][0]
        self.assertEqual((row["planned"], row["remaining"]), (5400, 5190))
        self.assertEqual(row["stats"]["total"], 40)

    def test_edit_and_delete_all_models(self):
        exam, subject, resource, second, study, practice = self.add_data()
        study_payload = {
            "subject": subject.pk,
            "resource": resource.pk,
            "date": format_jalali(self.today),
            "hours": "۳",
            "minutes": "۰",
        }
        self.assertEqual(
            self.client.post(f"/study/{study.pk}/edit/", study_payload).status_code, 302
        )
        study.refresh_from_db()
        self.assertEqual(study.duration_minutes, 180)
        practice_payload = {
            "subject": subject.pk,
            "date": format_jalali(self.today),
            "hours": "۰",
            "minutes": "۰",
            "correct_count": "۳۰",
            "wrong_count": "۰",
            "unanswered_count": "۰",
        }
        self.assertEqual(
            self.client.post(
                f"/practice/{practice.pk}/edit/", practice_payload
            ).status_code,
            302,
        )
        practice.refresh_from_db()
        self.assertEqual(practice.total_questions, 30)
        for route, instance in (
            ("study", study),
            ("practice", practice),
            ("resources", resource),
            ("subjects", subject),
        ):
            self.assertEqual(
                self.client.get(f"/{route}/{instance.pk}/delete/").status_code, 200
            )
            self.assertTrue(type(instance).objects.filter(pk=instance.pk).exists())
            self.assertEqual(
                self.client.post(f"/{route}/{instance.pk}/delete/").status_code, 302
            )
            self.assertFalse(type(instance).objects.filter(pk=instance.pk).exists())
        self.assertFalse(StudyResource.objects.exists())

    def test_csrf_required_for_delete(self):
        _, subject, *_ = self.add_data()
        secure_client = Client(enforce_csrf_checks=True)
        self.assertEqual(
            secure_client.post(f"/subjects/{subject.pk}/delete/").status_code, 403
        )
        self.assertTrue(Subject.objects.filter(pk=subject.pk).exists())

    def test_archive_preserves_history_and_excludes_workload(self):
        _, subject, resource, *_ = self.add_data()
        resource.is_active = False
        resource.save()
        row = subject_summaries()[0]
        self.assertEqual(row["planned_study"], 1200)
        self.assertEqual(row["actual_study"], 140)
        subject.is_active = False
        subject.save()
        self.assertEqual(dashboard_data()["remaining"], 0)
        self.assertEqual(dashboard_data()["stats"]["total"], 40)
        self.assertEqual(dashboard_data()["actual_study"], 140)
        self.assertContains(self.client.get("/subjects/"), "بایگانی‌شده")
        self.assertContains(self.client.get("/history/"), "ساختمان داده")

    def test_history_filters_invalid_date_and_pagination(self):
        _, subject, resource, *_ = self.add_data()
        for offset in range(25):
            StudySession.objects.create(
                resource=resource,
                duration_minutes=30,
                date=self.today - timedelta(days=offset),
            )
        page = self.client.get("/history/").context["page"]
        self.assertEqual((len(page), page.paginator.count), (20, 27))
        self.assertEqual(len(self.client.get("/history/?page=2").context["page"]), 7)
        response = self.client.get(
            "/history/",
            {
                "subject": subject.pk,
                "start_date": format_jalali(self.today),
                "end_date": format_jalali(self.today),
                "kind": "study",
            },
        )
        self.assertEqual(response.context["page"].paginator.count, 2)
        self.assertEqual(
            self.client.get("/history/?kind=practice").context["page"].paginator.count,
            1,
        )
        self.assertContains(self.client.get("/history/?start_date=bad"), "قالب")

    def test_output_is_escaped_and_assets_local(self):
        self.add_data()
        Subject.objects.create(name='<script>alert("x")</script>')
        response = self.client.get("/")
        self.assertNotContains(response, '<script>alert("x")</script>')
        self.assertContains(response, "&lt;script&gt;")
        for path in ("/", "/study/add/", "/practice/add/", "/history/", "/settings/"):
            body = self.client.get(path).content.decode()
            for token in (
                'src="http',
                'href="http',
                "googleapis",
                "jsdelivr",
                "unpkg",
                "cdnjs",
            ):
                self.assertNotIn(token, body)

    def test_subject_summary_queries_are_bounded(self):
        self.add_data()
        with self.assertNumQueries(5):
            subject_summaries()
        for index in range(10):
            subject = Subject.objects.create(name=f"درس {index}")
            StudyResource.objects.create(
                subject=subject, title="منبع", planned_minutes=100
            )
        with self.assertNumQueries(5):
            subject_summaries()

    def test_admin_forms(self):
        self.add_data()
        user = get_user_model().objects.create_superuser(
            "owner", "owner@example.test", "test-password-123"
        )
        self.client.force_login(user)
        for model in ("subject", "studyresource", "studysession", "practicesession"):
            with self.subTest(model=model):
                self.assertEqual(
                    self.client.get(reverse(f"admin:tracker_{model}_add")).status_code,
                    200,
                )
        self.assertEqual(
            self.client.get(
                reverse("admin:tracker_examsettings_change", args=[1])
            ).status_code,
            200,
        )


class StorageTests(TransactionTestCase):
    def test_live_backup_has_committed_data_and_integrity(self):
        subject = Subject.objects.create(name="دادهٔ پشتیبان")
        with (
            tempfile.TemporaryDirectory() as directory,
            override_settings(DATA_DIR=Path(directory)),
        ):
            output = io.StringIO()
            call_command("backup_db", stdout=output)
            files = list((Path(directory) / "backups").glob("*.sqlite3"))
            self.assertEqual(len(files), 1)
            with closing(sqlite3.connect(files[0])) as backup:
                self.assertEqual(
                    backup.execute("PRAGMA integrity_check").fetchall(), [("ok",)]
                )
                self.assertEqual(
                    backup.execute(
                        "SELECT name FROM tracker_subject WHERE id=?", [subject.pk]
                    ).fetchone()[0],
                    subject.name,
                )
            self.assertFalse(list(Path(directory).rglob("*.partial")))
            self.assertNotEqual(backup_database(), files[0])

    def test_real_file_wal_and_backup(self):
        # Django's default test DB is in memory and cannot enter WAL mode.
        # A separate real file uses exactly the application's connection options.
        with tempfile.TemporaryDirectory() as directory:
            config = deepcopy(connection.settings_dict)
            config["NAME"] = str(Path(directory) / "wal.sqlite3")
            database = DatabaseWrapper(config, alias="wal_verification")
            try:
                database.ensure_connection()
                raw = database.connection
                self.assertEqual(
                    raw.execute("PRAGMA journal_mode").fetchone()[0], "wal"
                )
                self.assertEqual(raw.execute("PRAGMA synchronous").fetchone()[0], 1)
                self.assertEqual(
                    raw.execute("PRAGMA busy_timeout").fetchone()[0], 20000
                )
                raw.execute("CREATE TABLE proof (value TEXT)")
                raw.execute("INSERT INTO proof VALUES ('committed WAL data')")
                with closing(
                    sqlite3.connect(Path(directory) / "backup.sqlite3")
                ) as backup:
                    raw.backup(backup)
                    self.assertEqual(
                        backup.execute("SELECT value FROM proof").fetchone()[0],
                        "committed WAL data",
                    )
                    self.assertEqual(
                        backup.execute("PRAGMA integrity_check").fetchone()[0], "ok"
                    )
            finally:
                database.close()

    def test_seed_demo_idempotent(self):
        output = io.StringIO()
        call_command("seed_demo", stdout=output)
        count = (
            Subject.objects.count(),
            StudyResource.objects.count(),
            StudySession.objects.count(),
            PracticeSession.objects.count(),
        )
        call_command("seed_demo", stdout=output)
        self.assertEqual(
            count,
            (
                Subject.objects.count(),
                StudyResource.objects.count(),
                StudySession.objects.count(),
                PracticeSession.objects.count(),
            ),
        )
        self.assertEqual(count, (3, 6, 18, 18))
