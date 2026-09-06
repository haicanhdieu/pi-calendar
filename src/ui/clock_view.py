"""Dirty-region Clock view renderer (FR3 / UX-DR1–3/9)."""

from src import config

# Precomputed digit strings — steady-state SS path never formats new strs.
_SS_STRINGS = (
    "00",
    "01",
    "02",
    "03",
    "04",
    "05",
    "06",
    "07",
    "08",
    "09",
    "10",
    "11",
    "12",
    "13",
    "14",
    "15",
    "16",
    "17",
    "18",
    "19",
    "20",
    "21",
    "22",
    "23",
    "24",
    "25",
    "26",
    "27",
    "28",
    "29",
    "30",
    "31",
    "32",
    "33",
    "34",
    "35",
    "36",
    "37",
    "38",
    "39",
    "40",
    "41",
    "42",
    "43",
    "44",
    "45",
    "46",
    "47",
    "48",
    "49",
    "50",
    "51",
    "52",
    "53",
    "54",
    "55",
    "56",
    "57",
    "58",
    "59",
)

_HH_STRINGS = (
    "00",
    "01",
    "02",
    "03",
    "04",
    "05",
    "06",
    "07",
    "08",
    "09",
    "10",
    "11",
    "12",
    "13",
    "14",
    "15",
    "16",
    "17",
    "18",
    "19",
    "20",
    "21",
    "22",
    "23",
)

_DOW = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
_MON = (
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
)


def _format_hhmm(local):
    if local is None:
        return config.CLOCK_PLACEHOLDER_HHMM
    return _HH_STRINGS[local.hour] + ":" + _SS_STRINGS[local.minute]


def _format_ss(local):
    if local is None:
        return None
    return _SS_STRINGS[local.second]


def _format_date(local):
    if local is None:
        return None
    # DOW · MON D YYYY — weekday Monday=0 (calendar epic convention)
    return (
        _DOW[local.weekday]
        + " · "
        + _MON[local.month - 1]
        + " "
        + str(local.day)
        + " "
        + str(local.year)
    )


class ClockView:
    """Centered 24-hour Clock renderer over DisplayPort only."""

    def __init__(self, display):
        self._display = display
        self._cache = {
            "hhmm": None,
            "ss": None,
            "date": None,
            "hour": None,
            "minute": None,
            "second": None,
            "year": None,
            "month": None,
            "day": None,
            "weekday": None,
            "has_local": None,
            "hhmm_x": 0,
            "hhmm_y": 0,
            "ss_x": 0,
            "ss_y": 0,
            "ss_w": 0,
            "ss_h": 0,
            "date_x": 0,
            "date_y": 0,
            "date_w": 0,
            "date_h": 0,
            "valid": False,
        }

    def invalidate(self):
        """Force full redraw on next render (view entry / badge base restore)."""
        self._cache["valid"] = False

    def render(self, snapshot):
        cache = self._cache
        local = snapshot.local

        if not cache["valid"]:
            self._full_redraw(
                _format_hhmm(local),
                _format_ss(local),
                _format_date(local),
            )
            self._remember_local(local)
            return

        # Identical content: no-op (avoids full redraw fallthrough).
        if local is None:
            if not cache["has_local"]:
                return
        elif (
            cache["has_local"]
            and cache["hour"] == local.hour
            and cache["minute"] == local.minute
            and cache["second"] == local.second
            and cache["year"] == local.year
            and cache["month"] == local.month
            and cache["day"] == local.day
            and cache["weekday"] == local.weekday
        ):
            return

        # Steady-state seconds-only path: field compares + precomputed SS string.
        if (
            local is not None
            and cache["has_local"]
            and cache["hour"] == local.hour
            and cache["minute"] == local.minute
            and cache["year"] == local.year
            and cache["month"] == local.month
            and cache["day"] == local.day
            and cache["weekday"] == local.weekday
            and cache["second"] != local.second
        ):
            ss = _SS_STRINGS[local.second]
            self._redraw_ss(ss)
            cache["ss"] = ss
            cache["second"] = local.second
            return

        self._full_redraw(
            _format_hhmm(local),
            _format_ss(local),
            _format_date(local),
        )
        self._remember_local(local)

    def _remember_local(self, local):
        cache = self._cache
        if local is None:
            cache["has_local"] = False
            cache["hour"] = None
            cache["minute"] = None
            cache["second"] = None
            cache["year"] = None
            cache["month"] = None
            cache["day"] = None
            cache["weekday"] = None
            return
        cache["has_local"] = True
        cache["hour"] = local.hour
        cache["minute"] = local.minute
        cache["second"] = local.second
        cache["year"] = local.year
        cache["month"] = local.month
        cache["day"] = local.day
        cache["weekday"] = local.weekday

    def _layout(self, hhmm, ss, date):
        display = self._display
        hhmm_w, hhmm_h = display.measure_text(hhmm, config.FONT_TIME)
        if ss is None:
            ss_w = 0
            ss_h = 0
            row_w = hhmm_w
            time_h = hhmm_h
        else:
            # Tabular SS slot always sized for "00" so trailer never reflows HH:MM.
            ss_w, ss_h = display.measure_text("00", config.FONT_SECONDS)
            row_w = hhmm_w + config.CLOCK_SS_GAP_PX + ss_w
            time_h = hhmm_h if hhmm_h >= ss_h else ss_h

        if date is not None:
            date_w, date_h = display.measure_text(date, config.FONT_DATE)
            block_h = time_h + config.CLOCK_DATE_GAP_PX + date_h
        else:
            date_w = 0
            date_h = 0
            block_h = time_h

        origin_x = (display.width - row_w) // 2
        origin_y = (display.height - block_h) // 2
        hhmm_x = origin_x
        hhmm_y = origin_y
        if ss is None:
            ss_x = 0
            ss_y = 0
        else:
            ss_x = origin_x + hhmm_w + config.CLOCK_SS_GAP_PX
            ss_y = origin_y + (hhmm_h - ss_h)
        date_x = (display.width - date_w) // 2
        date_y = origin_y + time_h + config.CLOCK_DATE_GAP_PX
        return (
            hhmm_x,
            hhmm_y,
            hhmm_w,
            hhmm_h,
            ss_x,
            ss_y,
            ss_w,
            ss_h,
            date_x,
            date_y,
            date_w,
            date_h,
        )

    def _full_redraw(self, hhmm, ss, date):
        display = self._display
        cache = self._cache
        display.fill_rect(
            0,
            0,
            display.width,
            display.height,
            config.COLOR_BACKGROUND,
        )

        (
            hhmm_x,
            hhmm_y,
            _hhmm_w,
            _hhmm_h,
            ss_x,
            ss_y,
            ss_w,
            ss_h,
            date_x,
            date_y,
            date_w,
            date_h,
        ) = self._layout(hhmm, ss, date)

        display.draw_text(hhmm, hhmm_x, hhmm_y, config.FONT_TIME, config.COLOR_PRIMARY)

        if ss is not None:
            display.draw_text(
                ss, ss_x, ss_y, config.FONT_SECONDS, config.COLOR_SECONDARY
            )

        if date is not None:
            display.draw_text(
                date, date_x, date_y, config.FONT_DATE, config.COLOR_SECONDARY
            )

        cache["hhmm"] = hhmm
        cache["ss"] = ss
        cache["date"] = date
        cache["hhmm_x"] = hhmm_x
        cache["hhmm_y"] = hhmm_y
        cache["ss_x"] = ss_x
        cache["ss_y"] = ss_y
        cache["ss_w"] = ss_w
        cache["ss_h"] = ss_h
        cache["date_x"] = date_x
        cache["date_y"] = date_y
        cache["date_w"] = date_w
        cache["date_h"] = date_h
        cache["valid"] = True

    def _redraw_ss(self, ss):
        display = self._display
        cache = self._cache
        display.fill_rect(
            cache["ss_x"],
            cache["ss_y"],
            cache["ss_w"],
            cache["ss_h"],
            config.COLOR_BACKGROUND,
        )
        if ss is not None:
            display.draw_text(
                ss,
                cache["ss_x"],
                cache["ss_y"],
                config.FONT_SECONDS,
                config.COLOR_SECONDARY,
            )
