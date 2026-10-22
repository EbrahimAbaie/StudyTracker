"""Pure calculations. Durations are minutes; no database or current-clock reads."""

from datetime import timedelta
from math import ceil


def percentage(completed, planned):
    return min(100.0, max(0.0, completed / planned * 100)) if planned > 0 else 0.0


def resource_progress(planned, actual, is_completed=False):
    remaining = 0 if is_completed else max(planned - actual, 0)
    return {
        "planned": planned,
        "actual": actual,
        "remaining": remaining,
        "completed": planned - remaining,
        "progress": percentage(planned - remaining, planned),
        "overrun": max(actual - planned, 0),
        "saved": max(planned - actual, 0) if is_completed else 0,
    }


def test_statistics(correct=0, wrong=0, unanswered=0):
    answered = correct + wrong
    total = answered + unanswered
    return {
        "correct": correct,
        "wrong": wrong,
        "unanswered": unanswered,
        "answered": answered,
        "total": total,
        "accuracy": correct / answered * 100 if answered else None,
        "answer_rate": answered / total * 100 if total else None,
    }


def subject_progress(
    resources, practice_target, actual_practice, question_target, stats
):
    planned_study = sum(row["planned"] for row in resources)
    remaining_study = sum(row["remaining"] for row in resources)
    planned_practice = practice_target or 0
    remaining_practice = max(planned_practice - actual_practice, 0)
    planned = planned_study + planned_practice
    remaining = remaining_study + remaining_practice
    return {
        "planned_study": planned_study,
        "remaining_study": remaining_study,
        "study_progress": percentage(planned_study - remaining_study, planned_study),
        "planned_practice": planned_practice,
        "actual_practice": actual_practice,
        "remaining_practice": remaining_practice,
        "practice_progress": percentage(
            min(actual_practice, planned_practice), planned_practice
        ),
        "has_practice_target": practice_target is not None,
        "question_target": question_target,
        "remaining_questions": max(question_target - stats["total"], 0)
        if question_target is not None
        else None,
        "extra_questions": max(stats["total"] - question_target, 0)
        if question_target is not None
        else 0,
        "planned": planned,
        "remaining": remaining,
        "completed": planned - remaining,
        "progress": percentage(planned - remaining, planned),
    }


def forecast(remaining_minutes, activities, today, exam_date=None, has_workload=True):
    """activities contains (date, minutes, session_count) daily aggregates.

    A question-only practice is an observation, but contributes no timed speed.
    Future-dated rows never enter the observation window.
    """
    history = [
        (day, minutes, count) for day, minutes, count in activities if day <= today
    ]
    base = {
        "weekly_average": 0,
        "observed_days": 0,
        "session_count": 0,
        "weeks_to_finish": None,
        "completion_date": None,
        "after_exam": False,
    }
    if not has_workload:
        return {**base, "label": "حجم کار زمانی تعیین نشده"}
    if remaining_minutes <= 0:
        return {**base, "label": "تکمیل شده"}
    if not history:
        return {**base, "label": "داده کافی برای تخمین وجود ندارد"}
    observed = min(28, (today - min(row[0] for row in history)).days + 1)
    start = today - timedelta(days=observed - 1)
    recent = [row for row in history if row[0] >= start]
    minutes = sum(row[1] for row in recent)
    sessions = sum(row[2] for row in recent)
    weekly = minutes / max(observed, 7) * 7
    base.update(weekly_average=weekly, observed_days=observed, session_count=sessions)
    if weekly <= 0:
        return {**base, "label": "داده زمانی کافی برای تخمین وجود ندارد"}
    weeks = remaining_minutes / weekly
    # datetime.date has a finite range; tiny measured speeds may exceed it.
    days = ceil(weeks * 7)
    try:
        completion = today + timedelta(days=days)
    except OverflowError:
        completion = None
    return {
        **base,
        "weeks_to_finish": weeks,
        "completion_date": completion,
        "after_exam": bool(
            exam_date and (completion is None or completion > exam_date)
        ),
        "label": "تخمین اولیه — داده هنوز کم است"
        if sessions < 3 or observed < 7
        else "تخمین بر اساس عملکرد اخیر",
    }


def capacity(exam_date, weekly_minutes, remaining, today):
    days = max((exam_date - today).days, 0)
    available = days / 7 * weekly_minutes
    return {
        "days_remaining": days,
        "exam_passed": exam_date < today,
        "exam_today": exam_date == today,
        "available": available,
        "buffer": available - remaining,
    }
