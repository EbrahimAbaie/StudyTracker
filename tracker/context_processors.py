from django.utils import timezone


def local_today(request):
    return {"today": timezone.localdate()}
