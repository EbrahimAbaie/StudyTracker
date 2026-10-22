from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone

from .utils import format_jalali


class ValidatedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="ایجاد")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="ویرایش")

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class ExamSettings(ValidatedModel):
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    title = models.CharField("عنوان آزمون", max_length=200)
    exam_date = models.DateField("تاریخ آزمون")
    weekly_available_minutes = models.PositiveIntegerField("ظرفیت هفتگی")

    class Meta:
        verbose_name = "تنظیمات آزمون"
        verbose_name_plural = "تنظیمات آزمون"
        constraints = [
            models.CheckConstraint(condition=Q(id=1), name="one_exam_settings")
        ]

    def __str__(self):
        return self.title


class Subject(ValidatedModel):
    name = models.CharField("نام درس", max_length=150, unique=True)
    order = models.PositiveIntegerField(
        "اولویت نمایش", default=1, validators=[MinValueValidator(1)]
    )
    is_active = models.BooleanField("فعال", default=True)
    practice_target_minutes = models.PositiveIntegerField(
        "هدف زمانی تست", null=True, blank=True
    )
    practice_target_questions = models.PositiveIntegerField(
        "هدف تعداد تست", null=True, blank=True
    )

    class Meta:
        ordering = ["order", "name"]
        verbose_name = "درس"
        verbose_name_plural = "درس‌ها"
        constraints = [
            models.CheckConstraint(
                condition=Q(order__gte=1), name="subject_positive_order"
            )
        ]

    def __str__(self):
        return self.name


class StudyResource(ValidatedModel):
    class Type(models.TextChoices):
        THEORY = "THEORY", "آموزش"
        TIPS_TEST = "TIPS_TEST", "نکته و تست"
        REVIEW = "REVIEW", "مرور"
        OTHER = "OTHER", "سایر"

    subject = models.ForeignKey(
        Subject, on_delete=models.CASCADE, related_name="resources", verbose_name="درس"
    )
    title = models.CharField("عنوان منبع", max_length=200)
    resource_type = models.CharField(
        "نوع منبع", max_length=12, choices=Type.choices, default=Type.THEORY
    )
    planned_minutes = models.PositiveIntegerField(
        "برآورد اولیه", validators=[MinValueValidator(1)]
    )
    order = models.PositiveIntegerField(
        "اولویت نمایش", default=1, validators=[MinValueValidator(1)]
    )
    is_active = models.BooleanField("فعال در حجم کار", default=True)
    is_completed = models.BooleanField("تکمیل شده", default=False)
    note = models.TextField("یادداشت", blank=True)

    class Meta:
        ordering = ["order", "title"]
        verbose_name = "منبع"
        verbose_name_plural = "منابع"
        constraints = [
            models.CheckConstraint(
                condition=Q(planned_minutes__gt=0), name="resource_positive_plan"
            ),
            models.CheckConstraint(
                condition=Q(order__gte=1), name="resource_positive_order"
            ),
        ]

    def __str__(self):
        return f"{self.subject} / {self.title}"


class StudySession(ValidatedModel):
    resource = models.ForeignKey(
        StudyResource,
        on_delete=models.CASCADE,
        related_name="study_sessions",
        verbose_name="منبع",
    )
    date = models.DateField("تاریخ", default=timezone.localdate, db_index=True)
    duration_minutes = models.PositiveIntegerField(
        "زمان مطالعه", validators=[MinValueValidator(1)]
    )
    note = models.TextField("یادداشت", blank=True)

    class Meta:
        ordering = ["-date", "-pk"]
        verbose_name = "مطالعه"
        verbose_name_plural = "مطالعه‌ها"
        indexes = [
            models.Index(fields=["resource", "date"], name="study_resource_date")
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(duration_minutes__gt=0), name="study_positive_duration"
            )
        ]

    def __str__(self):
        return f"{self.resource} ({format_jalali(self.date)})"


class PracticeSession(ValidatedModel):
    subject = models.ForeignKey(
        Subject,
        on_delete=models.CASCADE,
        related_name="practice_sessions",
        verbose_name="درس",
    )
    date = models.DateField("تاریخ", default=timezone.localdate, db_index=True)
    duration_minutes = models.PositiveIntegerField("زمان تست‌زنی", default=0)
    correct_count = models.PositiveIntegerField("صحیح", default=0)
    wrong_count = models.PositiveIntegerField("غلط", default=0)
    unanswered_count = models.PositiveIntegerField("نزده", default=0)
    note = models.TextField("یادداشت", blank=True)

    class Meta:
        ordering = ["-date", "-pk"]
        verbose_name = "تست‌زنی"
        verbose_name_plural = "تست‌زنی‌ها"
        indexes = [
            models.Index(fields=["subject", "date"], name="practice_subject_date")
        ]
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(duration_minutes__gt=0)
                    | Q(correct_count__gt=0)
                    | Q(wrong_count__gt=0)
                    | Q(unanswered_count__gt=0)
                ),
                name="practice_has_activity",
            )
        ]

    @property
    def total_questions(self):
        return self.correct_count + self.wrong_count + self.unanswered_count

    def clean(self):
        super().clean()
        values = [
            self.duration_minutes,
            self.correct_count,
            self.wrong_count,
            self.unanswered_count,
        ]
        if all(value is not None for value in values) and not any(
            value > 0 for value in values
        ):
            raise ValidationError("زمان تست‌زنی یا تعداد تست باید بیشتر از صفر باشد.")

    def __str__(self):
        return f"{self.subject} ({format_jalali(self.date)})"
