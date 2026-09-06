"""Pure Vietnamese lunar (âm lịch) civil conversion — no hardware imports.

Gregorian → lunar day/month/leap via Hồ Ngọc Đức's algorithm (UTC+7 /
105°E). Supported Gregorian years: 1900–2100 inclusive; inputs outside
that range raise ValueError.
"""

import math

# Vietnam civil timezone used by the Hồ Ngọc Đức reference algorithm.
_TIME_ZONE = 7.0
_PI = math.pi
_YEAR_MIN = 1900
_YEAR_MAX = 2100


def _floor(x):
    """INT(x) from the reference article: greatest integer not exceeding x."""
    return int(math.floor(x))


def _jd_from_date(dd, mm, yy):
    a = _floor((14 - mm) / 12)
    y = yy + 4800 - a
    m = mm + 12 * a - 3
    jd = (
        dd
        + _floor((153 * m + 2) / 5)
        + 365 * y
        + _floor(y / 4)
        - _floor(y / 100)
        + _floor(y / 400)
        - 32045
    )
    if jd < 2299161:
        jd = (
            dd
            + _floor((153 * m + 2) / 5)
            + 365 * y
            + _floor(y / 4)
            - 32083
        )
    return jd


def _new_moon_day(k, time_zone):
    t = k / 1236.85
    t2 = t * t
    t3 = t2 * t
    dr = _PI / 180
    jd1 = 2415020.75933 + 29.53058868 * k + 0.0001178 * t2 - 0.000000155 * t3
    jd1 = jd1 + 0.00033 * math.sin((166.56 + 132.87 * t - 0.009173 * t2) * dr)
    m = 359.2242 + 29.10535608 * k - 0.0000333 * t2 - 0.00000347 * t3
    mpr = 306.0253 + 385.81691806 * k + 0.0107306 * t2 + 0.00001236 * t3
    f = 21.2964 + 390.67050646 * k - 0.0016528 * t2 - 0.00000239 * t3
    c1 = (0.1734 - 0.000393 * t) * math.sin(m * dr) + 0.0021 * math.sin(
        2 * dr * m
    )
    c1 = c1 - 0.4068 * math.sin(mpr * dr) + 0.0161 * math.sin(dr * 2 * mpr)
    c1 = c1 - 0.0004 * math.sin(dr * 3 * mpr)
    c1 = c1 + 0.0104 * math.sin(dr * 2 * f) - 0.0051 * math.sin(
        dr * (m + mpr)
    )
    c1 = c1 - 0.0074 * math.sin(dr * (m - mpr)) + 0.0004 * math.sin(
        dr * (2 * f + m)
    )
    c1 = c1 - 0.0004 * math.sin(dr * (2 * f - m)) - 0.0006 * math.sin(
        dr * (2 * f + mpr)
    )
    c1 = c1 + 0.0010 * math.sin(dr * (2 * f - mpr)) + 0.0005 * math.sin(
        dr * (2 * mpr + m)
    )
    if t < -11:
        deltat = (
            0.001
            + 0.000839 * t
            + 0.0002261 * t2
            - 0.00000845 * t3
            - 0.000000081 * t * t3
        )
    else:
        deltat = -0.000278 + 0.000265 * t + 0.000262 * t2
    jd_new = jd1 + c1 - deltat
    return _floor(jd_new + 0.5 + time_zone / 24)


def _sun_longitude(jdn, time_zone):
    t = (jdn - 2451545.5 - time_zone / 24) / 36525
    t2 = t * t
    dr = _PI / 180
    m = 357.52910 + 35999.05030 * t - 0.0001559 * t2 - 0.00000048 * t * t2
    l0 = 280.46645 + 36000.76983 * t + 0.0003032 * t2
    dl = (1.914600 - 0.004817 * t - 0.000014 * t2) * math.sin(dr * m)
    dl = dl + (0.019993 - 0.000101 * t) * math.sin(dr * 2 * m)
    dl = dl + 0.000290 * math.sin(dr * 3 * m)
    l = (l0 + dl) * dr
    l = l - _PI * 2 * _floor(l / (_PI * 2))
    return _floor(l / _PI * 6)


def _lunar_month11(yy, time_zone):
    off = _jd_from_date(31, 12, yy) - 2415021
    k = _floor(off / 29.530588853)
    nm = _new_moon_day(k, time_zone)
    if _sun_longitude(nm, time_zone) >= 9:
        nm = _new_moon_day(k - 1, time_zone)
    return nm


def _leap_month_offset(a11, time_zone):
    k = _floor((a11 - 2415021.076998695) / 29.530588853 + 0.5)
    i = 1
    arc = _sun_longitude(_new_moon_day(k + i, time_zone), time_zone)
    last = 0
    while True:
        last = arc
        i += 1
        arc = _sun_longitude(_new_moon_day(k + i, time_zone), time_zone)
        if arc == last or i >= 14:
            break
    return i - 1


def gregorian_to_lunar(year, month, day):
    """
    Convert a Gregorian civil Y/M/D to Vietnamese lunar day/month/leap.

    Returns ``(lunar_day, lunar_month, is_leap)`` where ``lunar_day`` is
    1–30, ``lunar_month`` is 1–12, and ``is_leap`` is True for an
    intercalary (nhuận) month.

    Raises ``ValueError`` when ``year`` is outside 1900–2100.
    """
    if year < _YEAR_MIN or year > _YEAR_MAX:
        raise ValueError(
            "Gregorian year {} outside supported range {}–{}".format(
                year, _YEAR_MIN, _YEAR_MAX
            )
        )

    time_zone = _TIME_ZONE
    day_number = _jd_from_date(day, month, year)
    k = _floor((day_number - 2415021.076998695) / 29.530588853)
    month_start = _new_moon_day(k + 1, time_zone)
    if month_start > day_number:
        month_start = _new_moon_day(k, time_zone)

    a11 = _lunar_month11(year, time_zone)
    b11 = a11
    if a11 >= month_start:
        a11 = _lunar_month11(year - 1, time_zone)
    else:
        b11 = _lunar_month11(year + 1, time_zone)

    lunar_day = day_number - month_start + 1
    diff = _floor((month_start - a11) / 29)
    lunar_leap = False
    lunar_month = diff + 11

    if b11 - a11 > 365:
        leap_month_diff = _leap_month_offset(a11, time_zone)
        if diff >= leap_month_diff:
            lunar_month = diff + 10
            if diff == leap_month_diff:
                lunar_leap = True

    if lunar_month > 12:
        lunar_month = lunar_month - 12

    return lunar_day, lunar_month, lunar_leap
