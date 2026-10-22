from django.urls import path

from . import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("subjects/", views.subject_list, name="subject_list"),
    path("subjects/add/", views.subject_form, name="subject_add"),
    path("subjects/<int:pk>/", views.subject_detail, name="subject_detail"),
    path("subjects/<int:pk>/edit/", views.subject_form, name="subject_edit"),
    path(
        "subjects/<int:pk>/delete/",
        views.delete_object,
        {"kind": "subject"},
        name="subject_delete",
    ),
    path(
        "subjects/<int:subject_pk>/resources/add/",
        views.resource_form,
        name="resource_add",
    ),
    path("resources/<int:pk>/edit/", views.resource_form, name="resource_edit"),
    path(
        "resources/<int:pk>/delete/",
        views.delete_object,
        {"kind": "resource"},
        name="resource_delete",
    ),
    path("study/add/", views.study_form, name="study_add"),
    path("study/<int:pk>/edit/", views.study_form, name="study_edit"),
    path(
        "study/<int:pk>/delete/",
        views.delete_object,
        {"kind": "study"},
        name="study_delete",
    ),
    path("practice/add/", views.practice_form, name="practice_add"),
    path("practice/<int:pk>/edit/", views.practice_form, name="practice_edit"),
    path(
        "practice/<int:pk>/delete/",
        views.delete_object,
        {"kind": "practice"},
        name="practice_delete",
    ),
    path("history/", views.history, name="history"),
    path("settings/", views.settings_form, name="settings"),
    path("health/", views.health, name="health"),
]
