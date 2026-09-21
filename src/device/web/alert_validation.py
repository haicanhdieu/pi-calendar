"""Lazy Add Alert form validator; no device imports."""

class ValidationResult:
    __slots__ = ("ok", "reason", "settings")
    def __init__(self, ok, reason, settings=None):
        self.ok, self.reason, self.settings = ok, reason, settings


def validate_alert_id(alert_id):
    if (not isinstance(alert_id, str) or not alert_id or alert_id != alert_id.lower()
            or any(c not in "abcdefghijklmnopqrstuvwxyz0123456789-" for c in alert_id)):
        return ValidationResult(False, "fields")
    return ValidationResult(True, "ok")

def validate_alert_form_fields(fields, alert_id, alert_count):
    if not isinstance(fields, dict) or type(alert_count) is not int:
        return ValidationResult(False, "limit" if alert_count >= 10 else "fields")
    action = fields.get("alert_action")
    if action not in ("add", "edit"):
        return ValidationResult(False, "action")
    if action == "add" and alert_count >= 10:
        return ValidationResult(False, "limit")
    allowed = {"alert_action", "alert_time", "alert_enabled"}
    if action == "edit":
        allowed.add("alert_id")
    allowed.update("weekday_{}".format(i) for i in range(7))
    if any(k not in allowed for k in fields):
        return ValidationResult(False, "fields")
    value = fields.get("alert_time")
    if not isinstance(value, str) or len(value) != 5 or value[2] != ":":
        return ValidationResult(False, "time")
    try:
        hour, minute = int(value[:2]), int(value[3:])
    except (TypeError, ValueError):
        return ValidationResult(False, "time")
    if "{:02d}:{:02d}".format(hour, minute) != value or not 0 <= hour <= 23 or not 0 <= minute <= 59:
        return ValidationResult(False, "time")
    enabled = fields.get("alert_enabled")
    if enabled not in (None, "on"):
        return ValidationResult(False, "enabled")
    weekdays = []
    for i in range(7):
        key = "weekday_{}".format(i)
        if key in fields:
            if fields[key] != "on":
                return ValidationResult(False, "recurrence")
            weekdays.append(i)
    if action == "edit" and fields.get("alert_id") != alert_id:
        return ValidationResult(False, "fields")
    if not validate_alert_id(alert_id).ok:
        return ValidationResult(False, "fields")
    return ValidationResult(True, "ok", {
        "id": alert_id, "hour": hour, "minute": minute,
        "enabled": enabled == "on", "weekdays": weekdays,
    })
