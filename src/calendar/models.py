"""Pure Gregorian calendar domain types and annotation-kind ownership."""

# Lowercase kebab-case kinds owned here; providers may not invent kinds.
# Empty in v1 — lunar / enrichment stories extend this registry later.
ALLOWED_ANNOTATION_KINDS = ()

# Display / merge order for annotation kinds (parallel to ALLOWED_ANNOTATION_KINDS).
ANNOTATION_KIND_ORDER = ()


class CalendarAnnotation:
    """Semantic cell annotation; renderers own display formatting."""

    __slots__ = ("kind", "value")

    def __init__(self, kind, value):
        self.kind = kind
        self.value = value

    def __eq__(self, other):
        if not isinstance(other, CalendarAnnotation):
            return NotImplemented
        return self.kind == other.kind and self.value == other.value

    def __repr__(self):
        return "CalendarAnnotation(kind={!r}, value={!r})".format(
            self.kind, self.value
        )


class DayCell:
    """One grid cell: Gregorian civil date plus placement / today flags."""

    __slots__ = ("year", "month", "day", "in_month", "is_today", "annotations")

    def __init__(self, year, month, day, in_month, is_today, annotations=()):
        self.year = year
        self.month = month
        self.day = day
        self.in_month = in_month
        self.is_today = is_today
        self.annotations = annotations

    def __eq__(self, other):
        if not isinstance(other, DayCell):
            return NotImplemented
        return (
            self.year == other.year
            and self.month == other.month
            and self.day == other.day
            and self.in_month == other.in_month
            and self.is_today == other.is_today
            and self.annotations == other.annotations
        )

    def __repr__(self):
        return (
            "DayCell(year={}, month={}, day={}, in_month={}, is_today={}, "
            "annotations={!r})"
        ).format(
            self.year,
            self.month,
            self.day,
            self.in_month,
            self.is_today,
            self.annotations,
        )


class MonthGrid:
    """Monday-first weeks of DayCell records for one Gregorian month."""

    __slots__ = ("year", "month", "weeks")

    def __init__(self, year, month, weeks):
        self.year = year
        self.month = month
        self.weeks = weeks

    def __eq__(self, other):
        if not isinstance(other, MonthGrid):
            return NotImplemented
        return (
            self.year == other.year
            and self.month == other.month
            and self.weeks == other.weeks
        )

    def __repr__(self):
        return "MonthGrid(year={}, month={}, weeks={!r})".format(
            self.year, self.month, self.weeks
        )
