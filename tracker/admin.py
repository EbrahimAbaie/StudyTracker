from django.contrib import admin

from .forms import (
    ExamSettingsForm,
    PracticeSessionForm,
    ResourceForm,
    StudySessionForm,
    SubjectForm,
)
from .models import ExamSettings, PracticeSession, StudyResource, StudySession, Subject
from .utils import format_jalali


@admin.register(ExamSettings)
class ExamSettingsAdmin(admin.ModelAdmin):
    form = ExamSettingsForm
    list_display = ("title", "jalali_exam_date", "weekly_available_minutes")

    @admin.display(description="تاریخ آزمون", ordering="exam_date")
    def jalali_exam_date(self, obj):
        return format_jalali(obj.exam_date)

    def has_add_permission(self, request):
        return not ExamSettings.objects.exists() and super().has_add_permission(request)


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    form = SubjectForm
    list_display = (
        "name",
        "order",
        "is_active",
        "practice_target_minutes",
        "practice_target_questions",
    )
    search_fields = ("name",)
    list_filter = ("is_active",)
    ordering = ("order", "name")


@admin.register(StudyResource)
class ResourceAdmin(admin.ModelAdmin):
    form = ResourceForm
    # Subject is assigned by the ordinary admin model field.
    fields = (
        "subject",
        "title",
        "resource_type",
        "planned_hours",
        "planned_minutes_part",
        "order",
        "is_active",
        "is_completed",
        "note",
    )
    list_display = (
        "title",
        "subject",
        "resource_type",
        "planned_minutes",
        "is_active",
        "is_completed",
    )
    search_fields = ("title", "subject__name")
    list_filter = ("is_active", "is_completed", "resource_type", "subject")
    list_select_related = ("subject",)


@admin.register(StudySession)
class StudyAdmin(admin.ModelAdmin):
    form = StudySessionForm
    list_display = ("resource", "jalali_session_date", "duration_minutes")
    search_fields = ("resource__title", "resource__subject__name", "note")
    list_filter = ("date", "resource__subject")
    list_select_related = ("resource__subject",)

    @admin.display(description="تاریخ", ordering="date")
    def jalali_session_date(self, obj):
        return format_jalali(obj.date)


@admin.register(PracticeSession)
class PracticeAdmin(admin.ModelAdmin):
    form = PracticeSessionForm
    list_display = (
        "subject",
        "jalali_session_date",
        "duration_minutes",
        "correct_count",
        "wrong_count",
        "unanswered_count",
    )
    search_fields = ("subject__name", "note")
    list_filter = ("date", "subject")
    list_select_related = ("subject",)

    @admin.display(description="تاریخ", ordering="date")
    def jalali_session_date(self, obj):
        return format_jalali(obj.date)


admin.site.site_header = "مدیریت مسیر"
admin.site.site_title = "مسیر"
