"""Bounded query sets and aggregate reads; never one query per subject."""

from collections import defaultdict

from django.db.models import Count, Prefetch, Q, Sum
from django.utils import timezone

from .calculations import (
    capacity,
    forecast,
    percentage,
    resource_progress,
    subject_progress,
    test_statistics,
)
from .models import ExamSettings, PracticeSession, StudyResource, StudySession, Subject
from .utils import get_current_iranian_week_range


def subject_summaries(queryset=None, today=None, exam_date=None):
    today = today or timezone.localdate()
    subjects = list(
        (queryset if queryset is not None else Subject.objects.filter(is_active=True))
        .order_by("order", "name", "pk")
        .prefetch_related(
            Prefetch(
                "resources",
                queryset=StudyResource.objects.annotate(
                    actual=Sum("study_sessions__duration_minutes")
                ).order_by("order", "title", "pk"),
            )
        )
    )
    ids = [subject.pk for subject in subjects]
    practice = {
        row["subject_id"]: row
        for row in PracticeSession.objects.filter(subject_id__in=ids)
        .order_by()
        .values("subject_id")
        .annotate(
            minutes=Sum("duration_minutes"),
            correct=Sum("correct_count"),
            wrong=Sum("wrong_count"),
            unanswered=Sum("unanswered_count"),
        )
    }
    activity = defaultdict(list)
    for model, relation in (
        (StudySession, "resource__subject_id"),
        (PracticeSession, "subject_id"),
    ):
        daily = (
            model.objects.filter(**{f"{relation}__in": ids}, date__lte=today)
            .order_by()
            .values(relation, "date")
            .annotate(minutes=Sum("duration_minutes"), sessions=Count("pk"))
        )
        for row in daily:
            activity[row[relation]].append(
                (row["date"], row["minutes"], row["sessions"])
            )
    results = []
    for subject in subjects:
        resources = [
            {
                "resource": resource,
                **resource_progress(
                    resource.planned_minutes,
                    resource.actual or 0,
                    resource.is_completed,
                ),
            }
            for resource in subject.resources.all()
        ]
        active_resources = [row for row in resources if row["resource"].is_active]
        pr = practice.get(subject.pk, {})
        stats = test_statistics(
            pr.get("correct", 0), pr.get("wrong", 0), pr.get("unanswered", 0)
        )
        progress = subject_progress(
            active_resources,
            subject.practice_target_minutes,
            pr.get("minutes", 0),
            subject.practice_target_questions,
            stats,
        )
        actual_study = sum(row["actual"] for row in resources)
        results.append(
            {
                "subject": subject,
                "resources": resources,
                "stats": stats,
                **progress,
                "actual_study": actual_study,
                "actual_total": actual_study + pr.get("minutes", 0),
                "forecast": forecast(
                    progress["remaining"],
                    activity[subject.pk],
                    today,
                    exam_date,
                    has_workload=progress["planned"] > 0,
                ),
            }
        )
    return results


def dashboard_data(today=None):
    today = today or timezone.localdate()
    exam = ExamSettings.objects.first()
    subjects = subject_summaries(
        today=today, exam_date=exam.exam_date if exam else None
    )
    remaining = sum(row["remaining"] for row in subjects)
    planned = sum(row["planned"] for row in subjects)
    start, end = get_current_iranian_week_range(today)
    # The whole local week is displayed, but only activity through today is counted.
    study_totals = StudySession.objects.aggregate(
        total=Sum("duration_minutes"),
        weekly=Sum("duration_minutes", filter=Q(date__range=(start, today))),
    )
    practice_totals = PracticeSession.objects.aggregate(
        total=Sum("duration_minutes"),
        weekly=Sum("duration_minutes", filter=Q(date__range=(start, today))),
        correct=Sum("correct_count"),
        wrong=Sum("wrong_count"),
        unanswered=Sum("unanswered_count"),
    )
    weekly_study = study_totals["weekly"] or 0
    weekly_practice = practice_totals["weekly"] or 0
    stats = test_statistics(
        *(practice_totals[key] or 0 for key in ("correct", "wrong", "unanswered"))
    )
    return {
        "exam": exam,
        "subjects": subjects,
        "remaining": remaining,
        "planned": planned,
        "completed": planned - remaining,
        "progress": percentage(planned - remaining, planned),
        "actual_study": study_totals["total"] or 0,
        "actual_practice": practice_totals["total"] or 0,
        "stats": stats,
        "weekly_activity": weekly_study + weekly_practice,
        "weekly_study": weekly_study,
        "weekly_practice": weekly_practice,
        "weekly_progress": percentage(
            weekly_study + weekly_practice, exam.weekly_available_minutes
        )
        if exam
        else 0,
        "week_start": start,
        "week_end": end,
        "capacity": capacity(
            exam.exam_date, exam.weekly_available_minutes, remaining, today
        )
        if exam
        else None,
    }


def history_rows(filters):
    """UNION stays in SQLite, so pagination doesn't load every historic session."""
    from django.db.models import CharField, F, Value

    study = StudySession.objects.select_related("resource__subject")
    practice = PracticeSession.objects.select_related("subject")
    if filters.get("subject"):
        study = study.filter(resource__subject=filters["subject"])
        practice = practice.filter(subject=filters["subject"])
    for key, lookup in (("start_date", "date__gte"), ("end_date", "date__lte")):
        if filters.get(key):
            study = study.filter(**{lookup: filters[key]})
            practice = practice.filter(**{lookup: filters[key]})
    columns = (
        "id",
        "date",
        "duration_minutes",
        "note",
        "subject_name",
        "resource_title",
        "kind",
        "questions",
    )
    study = (
        study.order_by()
        .annotate(
            subject_name=F("resource__subject__name"),
            resource_title=F("resource__title"),
            kind=Value("study", output_field=CharField()),
            questions=Value(0),
        )
        .values(*columns)
    )
    practice = (
        practice.order_by()
        .annotate(
            subject_name=F("subject__name"),
            resource_title=Value("", output_field=CharField()),
            kind=Value("practice", output_field=CharField()),
            questions=F("correct_count") + F("wrong_count") + F("unanswered_count"),
        )
        .values(*columns)
    )
    if filters.get("kind") == "study":
        return study.order_by("-date", "-id")
    if filters.get("kind") == "practice":
        return practice.order_by("-date", "-id")
    return study.union(practice, all=True).order_by("-date", "-id", "kind")
