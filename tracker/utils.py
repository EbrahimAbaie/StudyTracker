import re
from datetime import date, datetime, timedelta

import jdatetime
from django.core.exceptions import ValidationError
from django.utils import timezone

DIGIT_TABLE = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
PERSIAN_TABLE = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")
MONTHS = (
    "فروردین",
    "اردیبهشت",
    "خرداد",
    "تیر",
    "مرداد",
    "شهریور",
    "مهر",
    "آبان",
    "آذر",
    "دی",
    "بهمن",
    "اسفند",
)
WEEKDAYS = ("دوشنبه", "سه‌شنبه", "چهارشنبه", "پنجشنبه", "جمعه", "شنبه", "یکشنبه")


def normalize_digits(value: object) -> str:
    return str(value).translate(DIGIT_TABLE) if value is not None else ""


def to_persian_digits(value: object) -> str:
    return str(value).translate(PERSIAN_TABLE)


def parse_jalali_date(value: str) -> date:
    text = normalize_digits(value).strip()
    if not re.fullmatch(r"[0-9]{4}/[0-9]{1,2}/[0-9]{1,2}", text):
        raise ValidationError("تاریخ شمسی را با قالب ۱۴۰۵/۰۸/۰۱ وارد کنید.")
    try:
        year, month, day = map(int, text.split("/"))
        return jdatetime.date(year, month, day).togregorian()
    except (ValueError, OverflowError) as exc:
        raise ValidationError("تاریخ شمسی معتبر نیست.") from exc


def format_jalali(value: date | datetime | None, style: str = "numeric") -> str:
    if not value:
        return "—"
    if isinstance(value, datetime):
        value = (
            timezone.localtime(value).date()
            if timezone.is_aware(value)
            else value.date()
        )
    if not isinstance(value, date):
        return "—"
    jalali = jdatetime.date.fromgregorian(date=value)
    if style in ("long", "full"):
        result = f"{jalali.day} {MONTHS[jalali.month - 1]} {jalali.year}"
        if style == "full":
            result = f"{WEEKDAYS[value.weekday()]} {result}"
    else:
        result = f"{jalali.year:04}/{jalali.month:02}/{jalali.day:02}"
    return to_persian_digits(result)


def format_duration(minutes):
    if minutes is None or minutes == "":
        return "—"
    value = int(round(abs(minutes)))
    hours, rest = divmod(value, 60)
    parts = []
    if hours:
        parts.append(f"{hours} ساعت")
    if rest or not parts:
        parts.append(f"{rest} دقیقه")
    return to_persian_digits(("−" if minutes < 0 else "") + " و ".join(parts))


def get_current_iranian_week_range(today: date | None = None) -> tuple[date, date]:
    today = today or timezone.localdate()
    start = today - timedelta(days=(today.weekday() - 5) % 7)
    return start, start + timedelta(days=6)
