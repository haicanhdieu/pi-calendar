"""Lazy authenticated Add Alert persistence path."""


def add_alert(fields, store):
    from src.device.web.alert_validation import validate_alert_form_fields
    settings = store.load()
    if not settings:
        return None, None, "Bad Request", 400
    alerts = list(settings.get("alerts", []))
    check = validate_alert_form_fields(fields, "alert-{}".format(len(alerts) + 1), len(alerts))
    if not check.ok:
        messages = {"limit": "Ten-alert limit reached.", "time": "Invalid Time.",
                    "enabled": "Invalid enabled state.", "recurrence": "Invalid recurrence.",
                    "action": "Invalid alert action.", "fields": "Invalid alert fields."}
        return settings, None, messages.get(check.reason, "Invalid alert."), 400
    alerts.append(check.settings)
    try:
        updated = store.commit(
            wifi_ssid=settings["wifi_ssid"], wifi_password=settings["wifi_password"],
            admin_salt_hex=settings["admin_salt"], admin_verifier_hex=settings["admin_verifier"],
            color_scheme=settings["color_scheme"], alerts=alerts,
            postpone_delay_minutes=settings.get("postpone_delay_minutes", 10),
        )
    except Exception:
        return settings, None, "Alert could not be saved.", 500
    return settings, updated, None, 200
