"""Lazy authenticated alert persistence paths."""


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


def edit_alert(fields, store):
    from src.device.web.alert_validation import validate_alert_form_fields
    settings = store.load()
    if not settings:
        return None, None, "Bad Request", 400
    alerts = list(settings.get("alerts", []))
    alert_id = fields.get("alert_id") if isinstance(fields, dict) else None
    index = None
    for i, alert in enumerate(alerts):
        if alert.get("id") == alert_id:
            index = i
            break
    if index is None:
        return settings, None, "Alert not found.", 400
    check = validate_alert_form_fields(fields, alert_id, len(alerts))
    if not check.ok:
        messages = {"time": "Invalid Time.", "enabled": "Invalid enabled state.",
                    "recurrence": "Invalid recurrence.", "fields": "Invalid alert fields.",
                    "action": "Invalid alert action."}
        return settings, None, messages.get(check.reason, "Invalid alert."), 400
    alerts[index] = check.settings
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


def delete_alert(fields, store):
    from src.device.web.alert_validation import validate_alert_id
    settings = store.load()
    if not settings:
        return None, None, "Bad Request", 400
    if (not isinstance(fields, dict) or len(fields) != 2
            or fields.get("alert_action") != "delete"):
        return settings, None, "Invalid alert action.", 400
    if "alert_id" not in fields:
        return settings, None, "Invalid alert fields.", 400
    alert_id = fields.get("alert_id")
    if not validate_alert_id(alert_id).ok:
        return settings, None, "Invalid alert id.", 400
    remaining = list(settings.get("alerts", []))
    match = -1
    for index, alert in enumerate(remaining):
        if alert.get("id") == alert_id:
            match = index
            break
    if match < 0:
        return settings, None, "Alert not found.", 400
    del remaining[match]
    try:
        updated = store.commit(
            wifi_ssid=settings["wifi_ssid"], wifi_password=settings["wifi_password"],
            admin_salt_hex=settings["admin_salt"], admin_verifier_hex=settings["admin_verifier"],
            color_scheme=settings["color_scheme"], alerts=remaining,
            postpone_delay_minutes=settings.get("postpone_delay_minutes", 10),
        )
    except Exception:
        return settings, None, "Alert could not be deleted.", 500
    return settings, updated, None, 200
