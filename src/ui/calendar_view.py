"""Current-month Calendar view renderer (FR5 / UX calendar chrome)."""

from src import config

# Full English uppercase month names — UI strings live only in the renderer.
# Month names and weekday initials packed into single strings.  As tuples of
# individual strs they were ~19 objects pinned on the Pico heap for the whole
# uptime; packed, each table is one object and a lookup allocates one
# short-lived str the collector reclaims immediately.
_MONTHS = (
    "JANUARY FEBRUARY MARCH APRIL MAY JUNE "
    "JULY AUGUST SEPTEMBER OCTOBER NOVEMBER DECEMBER "
)


def _month_name(month):
    start = 0
    for _ in range(month - 1):
        start = _MONTHS.index(" ", start) + 1
    return _MONTHS[start:_MONTHS.index(" ", start)]

# Monday-first single-letter weekday header (UX mockup).
_WEEKDAYS = "MTWTFSS"

_2DIGIT = (
    "000102030405060708091011121314151617181920212223242526272829"
    "303132333435363738394041424344454647484950515253545556575859"
)


def _format_hhmm(local):
    if local is None:
        return config.CLOCK_PLACEHOLDER_HHMM
    hour = local.hour * 2
    minute = local.minute * 2
    return _2DIGIT[hour:hour + 2] + ":" + _2DIGIT[minute:minute + 2]


def _format_month_label(year, month):
    return _month_name(month) + " " + str(year)


class CalendarView:
    """MonthGrid Calendar renderer over DisplayPort only (no badge draw)."""

    def __init__(self, display):
        self._display = display
        self._cache = {
            "valid": False,
            "year": None,
            "month": None,
            "weeks": None,
            "local_hour": None,
            "local_minute": None,
            "has_local": None,
        }

    def invalidate(self):
        """Force full redraw on next render (view entry / compositor restore)."""
        self._cache["valid"] = False

    def render(self, snapshot, grid):
        """
        Draw the Calendar chrome from an already-built MonthGrid.

        ``snapshot`` is accepted for compositor duck-typing; grid carries
        placement and today flags. Does not draw the unsynced badge.
        """
        cache = self._cache
        local = snapshot.local
        has_local = local is not None
        local_hour = local.hour if has_local else None
        local_minute = local.minute if has_local else None
        if (
            cache["valid"]
            and cache["year"] == grid.year
            and cache["month"] == grid.month
            and cache["weeks"] is grid.weeks
            and cache["has_local"] == has_local
            and cache["local_hour"] == local_hour
            and cache["local_minute"] == local_minute
        ):
            return

        self._full_redraw(grid, _format_hhmm(local))
        cache["valid"] = True
        cache["year"] = grid.year
        cache["month"] = grid.month
        cache["weeks"] = grid.weeks
        cache["has_local"] = has_local
        cache["local_hour"] = local_hour
        cache["local_minute"] = local_minute

    def _full_redraw(self, grid, clock_label):
        display = self._display
        display.fill_rect(
            0,
            0,
            display.width,
            display.height,
            config.COLOR_BACKGROUND,
        )
        clock_w, clock_h = display.measure_text(clock_label, config.FONT_BADGE)
        padding_x = config.CALENDAR_CLOCK_BOX_PADDING_X_PX
        padding_y = config.CALENDAR_CLOCK_BOX_PADDING_Y_PX
        display.fill_rect(
            0,
            0,
            clock_w + (2 * padding_x),
            clock_h + (2 * padding_y),
            config.COLOR_UNSYNCED,
        )
        display.draw_text(
            clock_label,
            padding_x,
            padding_y,
            config.FONT_BADGE,
            config.COLOR_WHITE,
        )

        content_x = config.CALENDAR_PAD_X
        content_y = config.CALENDAR_PAD_Y
        content_w = display.width - (2 * config.CALENDAR_PAD_X)
        content_h = display.height - (2 * config.CALENDAR_PAD_Y)

        label = _format_month_label(grid.year, grid.month)
        label_w, label_h = display.measure_text(label, config.FONT_MONTH)
        label_x = content_x + (content_w - label_w) // 2
        label_y = content_y
        display.draw_text(
            label,
            label_x,
            label_y,
            config.FONT_MONTH,
            config.COLOR_PRIMARY,
        )

        header_y = label_y + label_h + config.CALENDAR_LABEL_GAP
        _, weekday_h = display.measure_text("M", config.FONT_WEEKDAY)
        cell_w = (content_w - (6 * config.CALENDAR_GAP)) // 7

        for col, letter in enumerate(_WEEKDAYS):
            tw, th = display.measure_text(letter, config.FONT_WEEKDAY)
            cell_x = content_x + col * (cell_w + config.CALENDAR_GAP)
            tx = cell_x + (cell_w - tw) // 2
            ty = header_y + (weekday_h - th) // 2
            display.draw_text(
                letter,
                tx,
                ty,
                config.FONT_WEEKDAY,
                config.COLOR_SECONDARY,
            )

        n_rows = len(grid.weeks)
        grid_top = header_y + weekday_h + config.CALENDAR_HEADER_GAP
        grid_h = content_y + content_h - grid_top
        if n_rows > 0:
            cell_h = (grid_h - ((n_rows - 1) * config.CALENDAR_GAP)) // n_rows
        else:
            cell_h = 0

        for row_i, week in enumerate(grid.weeks):
            cell_y = grid_top + row_i * (cell_h + config.CALENDAR_GAP)
            for col, cell in enumerate(week):
                cell_x = content_x + col * (cell_w + config.CALENDAR_GAP)
                self._draw_day_cell(display, cell, cell_x, cell_y, cell_w, cell_h)

    def _draw_day_cell(self, display, cell, x, y, w, h):
        text = str(cell.day)
        tw, th = display.measure_text(text, config.FONT_DAY)
        tx = x + (w - tw) // 2
        ty = y + (h - th) // 2

        if cell.is_today:
            display.fill_rect(x, y, w, h, config.COLOR_PRIMARY)
            color = config.COLOR_BACKGROUND
        elif cell.in_month:
            color = config.COLOR_PRIMARY
        else:
            color = config.COLOR_SECONDARY

        display.draw_text(text, tx, ty, config.FONT_DAY, color)
