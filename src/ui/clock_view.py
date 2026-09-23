"""Dirty-region Clock view renderer (FR3 / UX-DR1–3/9)."""

from src import config
from src.calendar.lunar import gregorian_to_lunar

# Two-digit and label tables packed into one string each.  As tuples of
# individual strs these were ~100 separate objects pinned on the Pico heap for
# the device's whole uptime (see the settings-page heap work); packed, each
# table is a single object.  Slicing allocates one short-lived str per redraw,
# which the collector reclaims immediately, instead of holding every possible
# value resident forever.
#
# _2DIGIT covers 00..59, so the hour path (00..23) reads from the same table.
_2DIGIT = (
    "000102030405060708091011121314151617181920212223242526272829"
    "303132333435363738394041424344454647484950515253545556575859"
)
_DOW = "MonTueWedThuFriSatSun"
_MON = "JanFebMarAprMayJunJulAugSepOctNovDec"


def _two_digit(value):
    index = value * 2
    return _2DIGIT[index:index + 2]


def _label(table, index):
    start = index * 3
    return table[start:start + 3]


def _format_hhmm(local):
    if local is None:
        return config.CLOCK_PLACEHOLDER_HHMM
    return _two_digit(local.hour) + ":" + _two_digit(local.minute)


def _format_ss(local):
    if local is None:
        return None
    return _two_digit(local.second)


def _format_date(local):
    if local is None:
        return None
    # DOW · MON D YYYY — weekday Monday=0 (calendar epic convention)
    return (
        _label(_DOW, local.weekday)
        + " · "
        + _label(_MON, local.month - 1)
        + " "
        + str(local.day)
        + " "
        + str(local.year)
    )


def _format_lunar(local):
    """AL · D/M or AL · D/M+ (leap); None when local is absent.

    The "AL · " prefix identifies the string as the lunar (Am Lich) date.
    It no longer collides with the Gregorian date string because the lunar
    corner is rendered in its own smaller font (FONT_LUNAR) and distinct
    color (COLOR_LUNAR).
    """
    if local is None:
        return None
    try:
        lunar_day, lunar_month, is_leap = gregorian_to_lunar(
            local.year, local.month, local.day
        )
    except ValueError:
        # Out-of-range years: omit lunar line rather than abort redraw.
        return None
    text = "AL · " + str(lunar_day) + "/" + str(lunar_month)
    if is_leap:
        text = text + "+"
    return text


class ClockView:
    """24-hour Clock renderer: today top-left, luna-today top-right, clock
    centered below, with a reserved (undrawn) band at bottom for upcoming
    events. DisplayPort only."""

    def __init__(self, display):
        self._display = display
        self._cache = {
            "hhmm": None,
            "ss": None,
            "date": None,
            "lunar": None,
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
            "lunar_x": 0,
            "lunar_y": 0,
            "lunar_w": 0,
            "lunar_h": 0,
            "events": None,
            "pending_label": None,
            "valid": False,
        }

    def invalidate(self):
        """Force full redraw on next render (view entry / badge base restore)."""
        self._cache["valid"] = False

    def render(self, snapshot, events=None, pending_label=None):
        cache = self._cache
        local = snapshot.local

        if not cache["valid"]:
            self._full_redraw(
                _format_hhmm(local),
                _format_ss(local),
                _format_date(local),
                _format_lunar(local),
                events,
                pending_label,
            )
            self._remember_local(local)
            return

        # Identical content: no-op (avoids full redraw fallthrough).
        if local is None:
            if (not cache["has_local"] and cache["events"] == events
                    and cache["pending_label"] == pending_label):
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
            and cache["events"] == events
            and cache["pending_label"] == pending_label
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
            and cache["events"] == events
            and cache["pending_label"] == pending_label
        ):
            ss = _two_digit(local.second)
            self._redraw_ss(ss)
            cache["ss"] = ss
            cache["second"] = local.second
            return

        self._full_redraw(
            _format_hhmm(local),
            _format_ss(local),
            _format_date(local),
            _format_lunar(local),
            events,
            pending_label,
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

    def _layout(self, hhmm, ss, date, lunar):
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
        else:
            date_w = 0
            date_h = 0
        if lunar is not None:
            lunar_w, lunar_h = display.measure_text(lunar, config.FONT_LUNAR)
        else:
            lunar_w = 0
            lunar_h = 0

        # Today (top-left) / luna-today (top-right) corner row.
        corner_row_h = date_h if date_h >= lunar_h else lunar_h
        date_x = config.CLOCK_CORNER_PAD_X_PX
        date_y = config.CLOCK_CORNER_PAD_Y_PX
        lunar_x = display.width - lunar_w - config.CLOCK_CORNER_PAD_X_PX
        lunar_y = config.CLOCK_CORNER_PAD_Y_PX
        if corner_row_h:
            band_bottom = (
                config.CLOCK_CORNER_PAD_Y_PX
                + corner_row_h
                + config.CLOCK_CORNER_CLOCK_GAP_PX
            )
        else:
            band_bottom = 0

        # Clock centers in the space between the corner band and the
        # reserved (design-only, undrawn) upcoming-events band at bottom.
        available_top = band_bottom
        available_bottom = display.height - config.CLOCK_EVENTS_BAND_H_PX
        origin_x = (display.width - row_w) // 2
        origin_y = available_top + ((available_bottom - available_top - time_h) // 2)
        hhmm_x = origin_x
        hhmm_y = origin_y
        if ss is None:
            ss_x = 0
            ss_y = 0
        else:
            ss_x = origin_x + hhmm_w + config.CLOCK_SS_GAP_PX
            ss_y = origin_y + (hhmm_h - ss_h)
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
            lunar_x,
            lunar_y,
            lunar_w,
            lunar_h,
        )

    def _full_redraw(self, hhmm, ss, date, lunar, events=None, pending_label=None):
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
            lunar_x,
            lunar_y,
            lunar_w,
            lunar_h,
        ) = self._layout(hhmm, ss, date, lunar)

        display.draw_text(hhmm, hhmm_x, hhmm_y, config.FONT_TIME, config.COLOR_PRIMARY)

        if ss is not None:
            display.draw_text(
                ss, ss_x, ss_y, config.FONT_SECONDS, config.COLOR_SECONDARY
            )

        if date is not None:
            display.draw_text(
                date, date_x, date_y, config.FONT_DATE, config.COLOR_SECONDARY
            )

        if lunar is not None:
            display.draw_text(
                lunar, lunar_x, lunar_y, config.FONT_LUNAR, config.COLOR_LUNAR
            )

        self._draw_events(events if pending_label is None else None)
        self._draw_pending_button(pending_label)

        cache["hhmm"] = hhmm
        cache["ss"] = ss
        cache["date"] = date
        cache["lunar"] = lunar
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
        cache["lunar_x"] = lunar_x
        cache["lunar_y"] = lunar_y
        cache["lunar_w"] = lunar_w
        cache["lunar_h"] = lunar_h
        cache["events"] = list(events) if events else events
        cache["pending_label"] = pending_label
        cache["valid"] = True

    def _draw_pending_button(self, label):
        if label is None:
            return
        display = self._display
        band_top = display.height - config.CLOCK_EVENTS_BAND_H_PX
        display.fill_rect(
            0, band_top, display.width, config.CLOCK_EVENTS_BAND_H_PX,
            config.COLOR_SECONDARY,
        )
        width, height = display.measure_text(label, config.FONT_SETTINGS_STATUS)
        display.draw_text(
            label, (display.width - width) // 2,
            band_top + (config.CLOCK_EVENTS_BAND_H_PX - height) // 2,
            config.FONT_SETTINGS_STATUS, config.COLOR_BACKGROUND,
        )

    def _events_row_text(self, hhmm, title):
        """hhmm + "  " + title, char-truncated with a "..." suffix so the
        row's text never crosses CLOCK_EVENTS_ROW_RIGHT_PX."""
        display = self._display
        x = config.CLOCK_CORNER_PAD_X_PX
        if len(title) > 60:
            title = title[:60]
        text = hhmm + "  " + title
        width, _height = display.measure_text(text, config.FONT_SETTINGS_STATUS)
        if x + width <= config.CLOCK_EVENTS_ROW_RIGHT_PX:
            return text
        while title:
            title = title[:-1]
            text = hhmm + "  " + title + "..."
            width, _height = display.measure_text(text, config.FONT_SETTINGS_STATUS)
            if x + width <= config.CLOCK_EVENTS_ROW_RIGHT_PX:
                return text
        return hhmm + "  " + "..."

    def _draw_events(self, events):
        """Draw up to 3 pre-sorted (hhmm, title) rows in the reserved band."""
        if not events:
            return
        display = self._display
        x = config.CLOCK_CORNER_PAD_X_PX
        row_h = display.measure_text("Ag", config.FONT_SETTINGS_STATUS)[1]
        band_top = display.height - config.CLOCK_EVENTS_BAND_H_PX
        y = band_top + config.CLOCK_EVENTS_ROW_TOP_PAD_PX
        for hhmm, title in events[:3]:
            text = self._events_row_text(hhmm, title)
            display.draw_text(
                text, x, y, config.FONT_SETTINGS_STATUS, config.COLOR_SECONDARY
            )
            y += row_h + config.CLOCK_EVENTS_ROW_GAP_PX

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
