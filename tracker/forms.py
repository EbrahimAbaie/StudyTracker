from django import forms
from django.db.models import Q
from django.utils import timezone

from .models import ExamSettings, PracticeSession, StudyResource, StudySession, Subject
from .utils import format_jalali, normalize_digits, parse_jalali_date


class PersianIntegerField(forms.IntegerField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault(
            "widget", forms.TextInput(attrs={"inputmode": "numeric", "dir": "ltr"})
        )
        super().__init__(*args, **kwargs)

    def to_python(self, value):
        return super().to_python(normalize_digits(value))


class JalaliDateField(forms.DateField):
    widget = forms.TextInput

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("help_text", "تاریخ شمسی، مانند ۱۴۰۵/۰۸/۰۱")
        kwargs.setdefault(
            "widget", forms.TextInput(attrs={"dir": "ltr", "autocomplete": "off"})
        )
        super().__init__(*args, **kwargs)

    def to_python(self, value):
        if value in self.empty_values:
            return None
        # Model initial values remain actual Gregorian date objects.
        if not isinstance(value, str):
            return value
        return parse_jalali_date(value)

    def prepare_value(self, value):
        return format_jalali(value) if value and not isinstance(value, str) else value


class DurationModelForm(forms.ModelForm):
    """Each (model field, hours field, minute field, allow blank, allow zero)."""

    duration_specs = ()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for model_name, hour_name, minute_name, optional, zero in self.duration_specs:
            if self.instance.pk:
                value = getattr(self.instance, model_name)
                if value is not None:
                    self.initial[hour_name], self.initial[minute_name] = divmod(
                        value, 60
                    )
            elif not optional:
                self.initial.setdefault(hour_name, 0)
                self.initial.setdefault(minute_name, 0)
        for name, field in self.fields.items():
            if isinstance(field.widget, forms.Textarea):
                field.widget.attrs["rows"] = 3

    def clean(self):
        cleaned = super().clean()
        for model_name, hour_name, minute_name, optional, zero in self.duration_specs:
            if hour_name in self.errors or minute_name in self.errors:
                continue
            hours, minutes = cleaned.get(hour_name), cleaned.get(minute_name)
            if optional and hours is None and minutes is None:
                value = None
            else:
                value = (hours or 0) * 60 + (minutes or 0)
                if not zero and value <= 0:
                    self.add_error(hour_name, "مدت زمان باید بیشتر از صفر باشد.")
            setattr(self.instance, model_name, value)
        return cleaned


class SubjectForm(DurationModelForm):
    target_hours = PersianIntegerField(
        label="هدف زمانی تست: ساعت", min_value=0, required=False
    )
    target_minutes = PersianIntegerField(
        label="دقیقه", min_value=0, max_value=59, required=False
    )
    practice_target_questions = PersianIntegerField(
        label="هدف تعداد تست", min_value=0, required=False
    )
    order = PersianIntegerField(
        label="اولویت نمایش",
        min_value=1,
        initial=1,
        help_text="۱ بالاترین اولویت است؛ عددهای بزرگ‌تر بعدتر نمایش داده می‌شوند.",
    )
    duration_specs = (
        ("practice_target_minutes", "target_hours", "target_minutes", True, True),
    )

    class Meta:
        model = Subject
        fields = [
            "name",
            "target_hours",
            "target_minutes",
            "practice_target_questions",
            "order",
            "is_active",
        ]
        help_texts = {
            "is_active": "با غیرفعال کردن، درس بایگانی می‌شود و سوابق آن حفظ می‌شوند."
        }


class ResourceForm(DurationModelForm):
    planned_hours = PersianIntegerField(
        label="برآورد اولیه: ساعت", min_value=0, required=False
    )
    planned_minutes_part = PersianIntegerField(
        label="دقیقه", min_value=0, max_value=59, required=False
    )
    order = PersianIntegerField(
        label="اولویت نمایش",
        min_value=1,
        initial=1,
        help_text="۱ بالاترین اولویت است؛ عددهای بزرگ‌تر بعدتر نمایش داده می‌شوند.",
    )
    duration_specs = (
        ("planned_minutes", "planned_hours", "planned_minutes_part", False, False),
    )

    class Meta:
        model = StudyResource
        fields = [
            "title",
            "resource_type",
            "planned_hours",
            "planned_minutes_part",
            "order",
            "is_active",
            "is_completed",
            "note",
        ]
        help_texts = {
            "is_completed": "پیشرفت را ۱۰۰٪ می‌کند؛ برآورد اولیه و زمان واقعی حفظ می‌شوند.",
            "is_active": "منبع غیرفعال در حجم کار باقی‌مانده محاسبه نمی‌شود؛ سوابق آن حفظ می‌شوند.",
        }


class SessionForm(DurationModelForm):
    date = JalaliDateField(label="تاریخ")
    hours = PersianIntegerField(label="ساعت", min_value=0, required=False)
    minutes = PersianIntegerField(
        label="دقیقه", min_value=0, max_value=59, required=False
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.initial.setdefault("date", timezone.localdate())


class StudySessionForm(SessionForm):
    subject = forms.ModelChoiceField(label="درس", queryset=Subject.objects.none())
    duration_specs = (("duration_minutes", "hours", "minutes", False, False),)

    class Meta:
        model = StudySession
        fields = ["subject", "resource", "date", "hours", "minutes", "note"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        current_subject = (
            self.instance.resource.subject_id if self.instance.pk else None
        )
        self.fields["subject"].queryset = Subject.objects.filter(
            Q(is_active=True) | Q(pk=current_subject)
        )
        resources = StudyResource.objects.select_related("subject").filter(
            Q(is_active=True, subject__is_active=True) | Q(pk=self.instance.resource_id)
        )
        self.fields["resource"].queryset = resources
        if current_subject:
            self.initial["subject"] = current_subject
        self.resource_options = [
            {"id": r.pk, "subject": r.subject_id, "title": r.title} for r in resources
        ]

    def clean(self):
        cleaned = super().clean()
        resource, subject = cleaned.get("resource"), cleaned.get("subject")
        if resource and subject and resource.subject_id != subject.pk:
            self.add_error("resource", "منبع انتخابی متعلق به این درس نیست.")
        return cleaned


class PracticeSessionForm(SessionForm):
    correct_count = PersianIntegerField(label="صحیح", min_value=0, initial=0)
    wrong_count = PersianIntegerField(label="غلط", min_value=0, initial=0)
    unanswered_count = PersianIntegerField(label="نزده", min_value=0, initial=0)
    duration_specs = (("duration_minutes", "hours", "minutes", False, True),)

    class Meta:
        model = PracticeSession
        fields = [
            "subject",
            "date",
            "hours",
            "minutes",
            "correct_count",
            "wrong_count",
            "unanswered_count",
            "note",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["subject"].queryset = Subject.objects.filter(
            Q(is_active=True) | Q(pk=self.instance.subject_id)
        )


class ExamSettingsForm(DurationModelForm):
    exam_date = JalaliDateField(label="تاریخ آزمون")
    weekly_hours = PersianIntegerField(
        label="ظرفیت هفتگی: ساعت", min_value=0, required=False
    )
    weekly_minutes = PersianIntegerField(
        label="دقیقه", min_value=0, max_value=59, required=False
    )
    duration_specs = (
        ("weekly_available_minutes", "weekly_hours", "weekly_minutes", False, True),
    )

    class Meta:
        model = ExamSettings
        fields = ["title", "exam_date", "weekly_hours", "weekly_minutes"]


class HistoryFilterForm(forms.Form):
    subject = forms.ModelChoiceField(
        label="درس",
        queryset=Subject.objects.all(),
        required=False,
        empty_label="همه درس‌ها",
    )
    start_date = JalaliDateField(label="از تاریخ", required=False)
    end_date = JalaliDateField(label="تا تاریخ", required=False)
    kind = forms.ChoiceField(
        label="نوع فعالیت",
        required=False,
        choices=[("", "همه فعالیت‌ها"), ("study", "مطالعه"), ("practice", "تست‌زنی")],
    )

    def clean(self):
        cleaned = super().clean()
        start, end = cleaned.get("start_date"), cleaned.get("end_date")
        if start and end and start > end:
            raise forms.ValidationError("تاریخ شروع باید قبل از تاریخ پایان باشد.")
        return cleaned
