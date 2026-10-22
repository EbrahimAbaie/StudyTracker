from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from tracker.forms import (
    ExamSettingsForm,
    PracticeSessionForm,
    ResourceForm,
    StudySessionForm,
    SubjectForm,
)
from tracker.models import (
    ExamSettings,
    PracticeSession,
    StudyResource,
    StudySession,
    Subject,
)
from tracker.utils import format_jalali


class ModelTests(TestCase):
    def setUp(self):
        self.subject = Subject.objects.create(name="ساختمان داده")
        self.resource = StudyResource.objects.create(
            subject=self.subject, title="اصلی", planned_minutes=2400
        )

    def test_subject_validation(self):
        for kwargs in (
            {"practice_target_minutes": -1},
            {"practice_target_questions": -1},
            {"order": -1},
            {"order": 0},
        ):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValidationError):
                Subject(name="نام جدید", **kwargs).save()
        with self.assertRaises(ValidationError):
            Subject.objects.create(name=self.subject.name)

    def test_resource_plan_and_completion(self):
        for value in (0, -10):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                StudyResource(
                    subject=self.subject, title="خطا", planned_minutes=value
                ).save()
        self.resource.is_completed = True
        self.resource.save()
        self.resource.refresh_from_db()
        self.assertTrue(self.resource.is_completed)
        self.assertEqual(self.resource.planned_minutes, 2400)

    def test_resource_required_and_positive_study(self):
        with self.assertRaises(ValidationError):
            StudySession(duration_minutes=60).save()
        with self.assertRaises(ValidationError):
            StudySession(resource=self.resource, duration_minutes=0).save()
        with transaction.atomic(), self.assertRaises(IntegrityError):
            StudySession.objects.bulk_create([StudySession(duration_minutes=60)])

    def test_practice_validation(self):
        for kwargs in (
            {},
            {"correct_count": -1},
            {"duration_minutes": -1},
            {"wrong_count": -1},
            {"unanswered_count": -1},
        ):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValidationError):
                PracticeSession(subject=self.subject, **kwargs).save()
        self.assertEqual(
            PracticeSession.objects.create(
                subject=self.subject,
                correct_count=30,
                wrong_count=10,
                unanswered_count=10,
            ).total_questions,
            50,
        )
        self.assertEqual(
            PracticeSession.objects.create(
                subject=self.subject, duration_minutes=60
            ).total_questions,
            0,
        )
        practice = PracticeSession.objects.first()
        self.assertIn(format_jalali(practice.date), str(practice))
        study = StudySession.objects.create(resource=self.resource, duration_minutes=60)
        self.assertIn(format_jalali(study.date), str(study))

    def test_singleton(self):
        ExamSettings.objects.create(
            title="آزمون", exam_date=timezone.localdate(), weekly_available_minutes=1800
        )
        with self.assertRaises(ValidationError):
            ExamSettings.objects.create(
                title="دوم",
                exam_date=timezone.localdate(),
                weekly_available_minutes=1800,
            )
        with transaction.atomic(), self.assertRaises(IntegrityError):
            ExamSettings.objects.bulk_create(
                [
                    ExamSettings(
                        pk=2,
                        title="دوم",
                        exam_date=timezone.localdate(),
                        weekly_available_minutes=1800,
                    )
                ]
            )


class FormTests(TestCase):
    def setUp(self):
        self.subject = Subject.objects.create(name="ساختمان داده")
        self.resource = StudyResource.objects.create(
            subject=self.subject, title="اصلی", planned_minutes=2400
        )
        self.date = format_jalali(timezone.localdate())

    def study_data(self, **kwargs):
        return {
            "subject": self.subject.pk,
            "resource": self.resource.pk,
            "date": self.date,
            "hours": "۲",
            "minutes": "۲۰",
            **kwargs,
        }

    def test_study_persian_duration(self):
        form = StudySessionForm(self.study_data())
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.save().duration_minutes, 140)

    def test_all_numeric_alphabets(self):
        for hours, minutes in (("۲", "۲۰"), ("٢", "٢٠"), ("2", "20")):
            form = StudySessionForm(self.study_data(hours=hours, minutes=minutes))
            self.assertTrue(form.is_valid(), form.errors)
            self.assertEqual(form.save().duration_minutes, 140)

    def test_invalid_duration_is_form_error(self):
        for values in (
            {"hours": "۰", "minutes": "۰"},
            {"minutes": "۶۰"},
            {"hours": "-1"},
            {"minutes": "bad"},
        ):
            with self.subTest(values=values):
                self.assertFalse(StudySessionForm(self.study_data(**values)).is_valid())

    def test_mismatched_subject_resource(self):
        other = Subject.objects.create(name="سیستم عامل")
        form = StudySessionForm(self.study_data(subject=other.pk))
        self.assertFalse(form.is_valid())
        self.assertIn("resource", form.errors)

    def test_resource_cannot_be_empty(self):
        form = StudySessionForm(self.study_data(resource=""))
        self.assertFalse(form.is_valid())
        self.assertIn("resource", form.errors)

    def test_practice_digits_and_zero_duration(self):
        form = PracticeSessionForm(
            {
                "subject": self.subject.pk,
                "date": self.date,
                "hours": "۱",
                "minutes": "۱۰",
                "correct_count": "۲۹",
                "wrong_count": "٨",
                "unanswered_count": "۳",
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        session = form.save()
        self.assertEqual((session.duration_minutes, session.total_questions), (70, 40))

    def test_invalid_empty_practice(self):
        form = PracticeSessionForm(
            {
                "subject": self.subject.pk,
                "date": self.date,
                "hours": "0",
                "minutes": "0",
                "correct_count": "0",
                "wrong_count": "0",
                "unanswered_count": "0",
            }
        )
        self.assertFalse(form.is_valid())

    def test_today_initial_and_count_defaults(self):
        self.assertEqual(StudySessionForm().initial["date"], timezone.localdate())
        form = PracticeSessionForm()
        self.assertEqual(form.initial["date"], timezone.localdate())
        for name in ("correct_count", "wrong_count", "unanswered_count"):
            self.assertEqual(form[name].value(), 0)

    def test_subject_optional_targets_and_digits(self):
        form = SubjectForm(
            {
                "name": "سیستم عامل",
                "target_hours": "۳۰",
                "target_minutes": "۰",
                "practice_target_questions": "۲۰۰۰",
                "order": "١",
                "is_active": "on",
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        subject = form.save()
        self.assertEqual(
            (
                subject.practice_target_minutes,
                subject.practice_target_questions,
                subject.order,
            ),
            (1800, 2000, 1),
        )
        blank = SubjectForm({"name": "پایگاه داده", "order": "1", "is_active": "on"})
        self.assertTrue(blank.is_valid(), blank.errors)
        self.assertIsNone(blank.save().practice_target_minutes)

    def test_resource_completion_preserves_estimate(self):
        form = ResourceForm(
            {
                "title": "اصلی",
                "resource_type": "THEORY",
                "planned_hours": "۴۰",
                "planned_minutes_part": "۰",
                "order": "1",
                "is_active": "on",
                "is_completed": "on",
            },
            instance=self.resource,
        )
        self.assertTrue(form.is_valid(), form.errors)
        result = form.save()
        self.assertTrue(result.is_completed)
        self.assertEqual(result.planned_minutes, 2400)

    def test_exam_settings_persian_date_and_duration(self):
        form = ExamSettingsForm(
            {
                "title": "کنکور ۱۴۰۶",
                "exam_date": "۱۴۰۶/۰۲/۱۸",
                "weekly_hours": "۳۰",
                "weekly_minutes": "۰",
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.save().weekly_available_minutes, 1800)
