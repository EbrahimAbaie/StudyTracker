from datetime import date, timedelta

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from tracker.calculations import (
    capacity,
    forecast,
    resource_progress,
    subject_progress,
    test_statistics,
)
from tracker.utils import (
    format_duration,
    format_jalali,
    get_current_iranian_week_range,
    normalize_digits,
    parse_jalali_date,
)


class PresentationTests(SimpleTestCase):
    def test_all_digit_alphabets(self):
        for value in ("123", "۱۲۳", "١٢٣"):
            self.assertEqual(normalize_digits(value), "123")

    def test_all_date_alphabets(self):
        for value in ("۱۴۰۵/۰۸/۰۱", "١٤٠٥/٠٨/٠١", "1405/08/01"):
            self.assertEqual(parse_jalali_date(value), date(2026, 10, 23))

    def test_date_roundtrip_and_formats(self):
        day = date(2024, 3, 20)
        self.assertEqual(format_jalali(day), "۱۴۰۳/۰۱/۰۱")
        self.assertEqual(parse_jalali_date(format_jalali(day)), day)
        self.assertEqual(format_jalali(day, "long"), "۱ فروردین ۱۴۰۳")
        self.assertEqual(format_jalali(day, "full"), "چهارشنبه ۱ فروردین ۱۴۰۳")

    def test_leap_day_and_invalid_inputs(self):
        self.assertEqual(parse_jalali_date("1399/12/30"), date(2021, 3, 20))
        for value in (
            "1400/12/30",
            "1405/13/01",
            "1405/02/32",
            "1405/00/01",
            "2026-10-22",
            "bad",
        ):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                parse_jalali_date(value)

    def test_duration(self):
        self.assertEqual(format_duration(140), "۲ ساعت و ۲۰ دقیقه")
        self.assertEqual(format_duration(2800), "۴۶ ساعت و ۴۰ دقیقه")
        self.assertEqual(format_duration(0), "۰ دقیقه")
        self.assertEqual(format_duration(None), "—")
        self.assertEqual(format_duration(""), "—")

    def test_iranian_week(self):
        saturday = date(2026, 10, 17)
        for offset in range(7):
            self.assertEqual(
                get_current_iranian_week_range(saturday + timedelta(days=offset)),
                (saturday, saturday + timedelta(days=6)),
            )


class ProgressTests(SimpleTestCase):
    def test_resource_normal(self):
        result = resource_progress(2400, 840)
        self.assertEqual((result["remaining"], result["progress"]), (1560, 35))

    def test_overrun_keeps_actual(self):
        result = resource_progress(2400, 2700)
        self.assertEqual(
            (
                result["remaining"],
                result["progress"],
                result["actual"],
                result["overrun"],
            ),
            (0, 100, 2700, 300),
        )

    def test_manual_completion(self):
        result = resource_progress(1200, 840, True)
        self.assertEqual(
            (
                result["planned"],
                result["actual"],
                result["remaining"],
                result["progress"],
                result["saved"],
            ),
            (1200, 840, 0, 100, 360),
        )

    def test_subject_workload(self):
        resources = [resource_progress(2400, 140), resource_progress(1200, 840, True)]
        result = subject_progress(resources, 1800, 70, 2000, test_statistics(29, 8, 3))
        self.assertEqual(result["planned"], 5400)
        self.assertEqual(result["remaining"], 2260 + 1730)
        self.assertEqual(result["completed"], 1410)
        self.assertEqual(result["remaining_questions"], 1960)

    def test_no_practice_target_does_not_inflate_progress(self):
        result = subject_progress(
            [resource_progress(600, 60)], None, 2000, None, test_statistics()
        )
        self.assertEqual(
            (result["planned"], result["remaining"], result["progress"]), (600, 540, 10)
        )
        self.assertFalse(result["has_practice_target"])

    def test_zero_and_question_overrun(self):
        result = subject_progress([], 0, 100, 20, test_statistics(25))
        self.assertEqual(result["progress"], 0)
        self.assertEqual(result["remaining_questions"], 0)
        self.assertEqual(result["extra_questions"], 5)

    def test_test_statistics(self):
        stats = test_statistics(30, 10, 10)
        self.assertEqual(
            (
                stats["total"],
                stats["answered"],
                stats["accuracy"],
                stats["answer_rate"],
            ),
            (50, 40, 75, 80),
        )
        self.assertIsNone(test_statistics()["accuracy"])
        self.assertIsNone(test_statistics()["answer_rate"])

    def test_capacity_and_past_exam(self):
        today = date(2026, 10, 22)
        result = capacity(today + timedelta(days=14), 1800, 4000, today)
        self.assertEqual((result["available"], result["buffer"]), (3600, -400))
        past = capacity(today - timedelta(days=1), 1800, 0, today)
        self.assertEqual(past["days_remaining"], 0)
        self.assertTrue(past["exam_passed"])


class ForecastTests(SimpleTestCase):
    today = date(2026, 10, 22)

    def test_fresh_subject_is_not_divided_by_four(self):
        result = forecast(1800, [(self.today, 180, 1)], self.today)
        self.assertEqual(result["weekly_average"], 180)
        self.assertEqual(result["observed_days"], 1)
        self.assertIn("تخمین اولیه", result["label"])
        self.assertEqual(result["completion_date"], self.today + timedelta(days=70))

    def test_no_activity(self):
        result = forecast(100, [], self.today)
        self.assertIsNone(result["completion_date"])
        self.assertIn("کافی", result["label"])

    def test_fewer_than_three_sessions(self):
        result = forecast(
            100,
            [(self.today - timedelta(days=10), 100, 1), (self.today, 100, 1)],
            self.today,
        )
        self.assertIn("تخمین اولیه", result["label"])

    def test_seven_days_with_three_sessions(self):
        rows = [
            (self.today - timedelta(days=6), 60, 1),
            (self.today - timedelta(days=3), 60, 1),
            (self.today, 60, 1),
        ]
        result = forecast(180, rows, self.today)
        self.assertEqual(result["observed_days"], 7)
        self.assertEqual(result["weekly_average"], 180)
        self.assertEqual(result["label"], "تخمین بر اساس عملکرد اخیر")

    def test_window_is_inclusive_28_days(self):
        rows = [
            (self.today - timedelta(days=50), 10000, 1),
            (self.today - timedelta(days=28), 10000, 1),
            (self.today - timedelta(days=27), 120, 1),
            (self.today, 120, 2),
        ]
        result = forecast(600, rows, self.today)
        self.assertEqual(
            (
                result["observed_days"],
                result["weekly_average"],
                result["session_count"],
            ),
            (28, 60, 3),
        )

    def test_completed(self):
        self.assertEqual(forecast(0, [], self.today)["label"], "تکمیل شده")

    def test_late_completion(self):
        self.assertTrue(
            forecast(
                600, [(self.today, 60, 1)], self.today, self.today + timedelta(days=5)
            )["after_exam"]
        )

    def test_future_and_zero_time_activity(self):
        result = forecast(600, [(self.today + timedelta(days=1), 600, 1)], self.today)
        self.assertEqual(result["weekly_average"], 0)
        self.assertIsNone(result["completion_date"])
        zero = forecast(600, [(self.today, 0, 1)], self.today)
        self.assertIsNone(zero["completion_date"])

    def test_no_workload_is_not_labelled_completed(self):
        self.assertEqual(
            forecast(0, [], self.today, has_workload=False)["label"],
            "حجم کار زمانی تعیین نشده",
        )
