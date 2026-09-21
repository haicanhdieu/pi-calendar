"""Lazy authenticated postpone-delay page and persistence path."""

from src.device.web.http_parse import html_escape


def postpone_section_html(postpone, saved=False, error=None):
    feedback = ''
    if saved:
        feedback = '<p class="banner success" aria-live="polite">Postpone delay saved.</p>'
    if error:
        feedback += '<p class="banner danger" role="alert">{}</p>'.format(html_escape(error))
    return ('<section><h2>POSTPONE</h2>{}'
            '<form method="POST" action="/settings"><input name="postpone_action" '
            'value="save" type="hidden"><label>Postpone delay (min)'
            '<input name="postpone_delay_minutes" type="number" min="1" max="60" '
            'step="1" value="{}"></label> minutes '
            '<button>Save</button></form>').format(feedback, html_escape(str(postpone)))


def validate_postpone_delay(value):
    """Return canonical whole-minute delay, or ``None`` when invalid."""
    if not isinstance(value, str) or not value.isdigit():
        return None
    try:
        delay = int(value)
    except (TypeError, ValueError):
        return None
    if not 1 <= delay <= 60:
        return None
    return delay


def save_postpone_delay(fields, store):
    """Validate and atomically save delay while preserving complete settings."""
    settings = store.load()
    if not settings:
        return None, None, "Bad Request", 400
    if (not isinstance(fields, dict) or len(fields) != 2
            or fields.get("postpone_action") != "save"
            or "postpone_delay_minutes" not in fields):
        return settings, None, "Postpone delay must be 1 to 60 whole minutes.", 400
    delay = validate_postpone_delay(fields["postpone_delay_minutes"])
    if delay is None:
        return settings, None, "Postpone delay must be 1 to 60 whole minutes.", 400
    try:
        updated = store.commit(
            wifi_ssid=settings["wifi_ssid"], wifi_password=settings["wifi_password"],
            admin_salt_hex=settings["admin_salt"], admin_verifier_hex=settings["admin_verifier"],
            color_scheme=settings["color_scheme"], alerts=list(settings.get("alerts", [])),
            postpone_delay_minutes=delay,
        )
    except Exception:
        return settings, None, "Postpone delay could not be saved.", 500
    return settings, updated, None, 200
