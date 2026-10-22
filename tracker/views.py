from django.contrib import messages
from django.core.paginator import Paginator
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods, require_safe

from .forms import (
    ExamSettingsForm,
    HistoryFilterForm,
    PracticeSessionForm,
    ResourceForm,
    StudySessionForm,
    SubjectForm,
)
from .models import ExamSettings, PracticeSession, StudyResource, StudySession, Subject
from .selectors import dashboard_data, history_rows, subject_summaries
from .services import save_form


@require_safe
def dashboard(request):
    return render(request, "dashboard.html", dashboard_data())


@require_safe
def subject_list(request):
    exam = ExamSettings.objects.first()
    return render(
        request,
        "subject_list.html",
        {
            "subjects": subject_summaries(
                Subject.objects.all(), exam_date=exam.exam_date if exam else None
            ),
        },
    )


@require_safe
def subject_detail(request, pk):
    subject = get_object_or_404(Subject, pk=pk)
    exam = ExamSettings.objects.first()
    summary = subject_summaries(
        Subject.objects.filter(pk=pk), exam_date=exam.exam_date if exam else None
    )[0]
    return render(
        request,
        "subject_detail.html",
        {
            "row": summary,
            "latest_study": StudySession.objects.filter(
                resource__subject=subject
            ).select_related("resource")[:5],
            "latest_practice": PracticeSession.objects.filter(subject=subject)[:5],
        },
    )


def form_response(
    request, form, template, title, success_url, success_message, **context
):
    if request.method == "POST" and form.is_valid():
        save_form(form)
        messages.success(request, success_message)
        return redirect(success_url)
    return render(
        request,
        template,
        {"form": form, "title": title, "cancel_url": success_url, **context},
    )


@require_http_methods(["GET", "POST"])
def subject_form(request, pk=None):
    instance = get_object_or_404(Subject, pk=pk) if pk else Subject()
    form = SubjectForm(
        request.POST if request.method == "POST" else None, instance=instance
    )
    return form_response(
        request,
        form,
        "subject_form.html",
        "ویرایش درس" if pk else "افزودن درس",
        reverse("subject_detail", args=[pk]) if pk else reverse("subject_list"),
        "درس با موفقیت ذخیره شد.",
    )


@require_http_methods(["GET", "POST"])
def resource_form(request, subject_pk=None, pk=None):
    instance = (
        get_object_or_404(StudyResource.objects.select_related("subject"), pk=pk)
        if pk
        else StudyResource(subject=get_object_or_404(Subject, pk=subject_pk))
    )
    form = ResourceForm(
        request.POST if request.method == "POST" else None, instance=instance
    )
    return form_response(
        request,
        form,
        "resource_form.html",
        "ویرایش منبع" if pk else "افزودن منبع",
        reverse("subject_detail", args=[instance.subject_id]),
        "منبع با موفقیت ذخیره شد.",
        subject=instance.subject,
    )


@require_http_methods(["GET", "POST"])
def study_form(request, pk=None):
    instance = (
        get_object_or_404(
            StudySession.objects.select_related("resource__subject"), pk=pk
        )
        if pk
        else StudySession()
    )
    initial = {
        "subject": request.GET.get("subject"),
        "resource": request.GET.get("resource"),
    }
    form = StudySessionForm(
        request.POST if request.method == "POST" else None,
        instance=instance,
        initial=initial,
    )
    return form_response(
        request,
        form,
        "study_session_form.html",
        "ویرایش مطالعه" if pk else "ثبت مطالعه",
        reverse("history") if pk else reverse("dashboard"),
        "مطالعه با موفقیت ثبت شد.",
        resource_options=form.resource_options,
    )


@require_http_methods(["GET", "POST"])
def practice_form(request, pk=None):
    instance = get_object_or_404(PracticeSession, pk=pk) if pk else PracticeSession()
    form = PracticeSessionForm(
        request.POST if request.method == "POST" else None,
        instance=instance,
        initial={"subject": request.GET.get("subject")},
    )
    return form_response(
        request,
        form,
        "practice_session_form.html",
        "ویرایش تست‌زنی" if pk else "ثبت تست",
        reverse("history") if pk else reverse("dashboard"),
        "تست‌زنی با موفقیت ثبت شد.",
    )


@require_http_methods(["GET", "POST"])
def settings_form(request):
    instance = ExamSettings.objects.first() or ExamSettings()
    form = ExamSettingsForm(
        request.POST if request.method == "POST" else None, instance=instance
    )
    return form_response(
        request,
        form,
        "settings_form.html",
        "تنظیمات آزمون",
        reverse("dashboard"),
        "تنظیمات با موفقیت ذخیره شد.",
    )


@require_http_methods(["GET", "POST"])
def delete_object(request, pk, kind):
    config = {
        "subject": (Subject, "subject_confirm_delete.html"),
        "resource": (StudyResource, "resource_confirm_delete.html"),
        "study": (StudySession, "study_session_confirm_delete.html"),
        "practice": (PracticeSession, "practice_session_confirm_delete.html"),
    }
    model, template = config[kind]
    instance = get_object_or_404(model, pk=pk)
    destination = (
        reverse("subject_list")
        if kind == "subject"
        else reverse("subject_detail", args=[instance.subject_id])
        if kind == "resource"
        else reverse("history")
    )
    if request.method == "POST":
        instance.delete()
        messages.success(request, "حذف با موفقیت انجام شد.")
        return redirect(destination)
    related = None
    if kind == "subject":
        related = {
            "resources": instance.resources.count(),
            "study": StudySession.objects.filter(resource__subject=instance).count(),
            "practice": instance.practice_sessions.count(),
        }
    elif kind == "resource":
        related = {"study": instance.study_sessions.count()}
    return render(
        request,
        template,
        {
            "object": instance,
            "kind": kind,
            "related": related,
            "cancel_url": destination,
        },
    )


@require_safe
def history(request):
    form = HistoryFilterForm(request.GET)
    rows = history_rows(form.cleaned_data) if form.is_valid() else []
    page = Paginator(rows, 20).get_page(request.GET.get("page"))
    query = request.GET.copy()
    query.pop("page", None)
    return render(
        request,
        "history.html",
        {"form": form, "page": page, "filter_query": query.urlencode()},
    )


@require_safe
def health(request):
    return HttpResponse("OK", content_type="text/plain")
