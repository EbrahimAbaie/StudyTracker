from django import template

from tracker.utils import format_duration, format_jalali, to_persian_digits

register = template.Library()
register.filter("jalali_date", format_jalali)
register.filter("duration", format_duration)
register.filter("fa", to_persian_digits)


@register.filter
def percent(value):
    return "—" if value is None else to_persian_digits(f"{value:.1f}٪")
