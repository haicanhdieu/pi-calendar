"""Pure Gregorian month-grid generation (Monday=0, no hardware imports)."""

from src.calendar.models import DayCell, MonthGrid

# Sakamoto offsets; formula yields Sunday=0 before conversion to Monday=0.
_SAKAMOTO_T = (0, 3, 2, 5, 0, 3, 5, 1, 4, 6, 2, 4)


def days_in_month(year, month):
    """Gregorian month length (%4 / %100 / %400 leap rule)."""
    if month == 2:
        leap = year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)
        return 29 if leap else 28
    if month in (4, 6, 9, 11):
        return 30
    return 31


def weekday_from_ymd(year, month, day):
    """
    Civil weekday from (year, month, day).

    Returns Monday=0 … Sunday=6. Does not use RTC / DateTime.weekday.
    """
    y = year - (1 if month < 3 else 0)
    w_sun0 = (
        y + y // 4 - y // 100 + y // 400 + _SAKAMOTO_T[month - 1] + day
    ) % 7
    return (w_sun0 + 6) % 7


def _prev_month(year, month):
    if month == 1:
        return year - 1, 12
    return year, month - 1


def _next_month(year, month):
    if month == 12:
        return year + 1, 1
    return year, month + 1


def build_month_grid(local_year, local_month, today_year, today_month, today_day):
    """
    Build a Monday-first MonthGrid for ``local_year``/``local_month``.

    Adjacent-month overflow cells have ``in_month=False``. ``is_today`` is set
    when the cell's civil date matches today. Annotations are always empty.
    """
    dim = days_in_month(local_year, local_month)
    first_wd = weekday_from_ymd(local_year, local_month, 1)

    prev_y, prev_m = _prev_month(local_year, local_month)
    prev_dim = days_in_month(prev_y, prev_m)

    cells = []
    for i in range(first_wd):
        d = prev_dim - first_wd + 1 + i
        cells.append(
            DayCell(
                year=prev_y,
                month=prev_m,
                day=d,
                in_month=False,
                is_today=(
                    prev_y == today_year
                    and prev_m == today_month
                    and d == today_day
                ),
                annotations=(),
            )
        )

    for d in range(1, dim + 1):
        cells.append(
            DayCell(
                year=local_year,
                month=local_month,
                day=d,
                in_month=True,
                is_today=(
                    local_year == today_year
                    and local_month == today_month
                    and d == today_day
                ),
                annotations=(),
            )
        )

    next_y, next_m = _next_month(local_year, local_month)
    trail = (7 - (len(cells) % 7)) % 7
    for d in range(1, trail + 1):
        cells.append(
            DayCell(
                year=next_y,
                month=next_m,
                day=d,
                in_month=False,
                is_today=(
                    next_y == today_year
                    and next_m == today_month
                    and d == today_day
                ),
                annotations=(),
            )
        )

    weeks = []
    for i in range(0, len(cells), 7):
        weeks.append(tuple(cells[i : i + 7]))

    return MonthGrid(year=local_year, month=local_month, weeks=tuple(weeks))
