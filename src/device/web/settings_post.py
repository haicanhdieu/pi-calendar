"""Lazy authenticated settings POST handlers."""

from src.device.web import pages
from src.device.web.http_parse import parse_form_urlencoded
from src.provisioning.validation import validate_admin_password_field


def route(request, session_table, now, kdf_busy, settings_store, lookup, result):
    entry, reject = lookup(request, session_table, now)
    if reject is not None:
        return reject
    if kdf_busy:
        return result("respond", pages.response_busy())
    ctype = request.headers.get("content-type", "")
    if ctype and "application/x-www-form-urlencoded" not in ctype.lower():
        return result("respond", pages.response_bad_request())
    fields = parse_form_urlencoded(request.body)
    if fields is None:
        return result("respond", pages.response_bad_request())
    if fields.get("postpone_action") == "save":
        from src.device.web.postpone_route import save_postpone_delay
        settings, updated, error, status = save_postpone_delay(fields, settings_store)
        if error:
            if settings is None:
                return result("respond", pages.response_bad_request())
            return result("respond", pages.response_settings_page(
                settings=settings, postpone_error=error, status_code=status,
            ))
        return result("respond", pages.response_settings_page(
            settings=updated, postpone_saved=True
        ), renew_session_id=entry.encoded_id)
    if fields.get("alert_action") == "add":
        from src.device.web.alert_route import add_alert
        settings, updated, error, status = add_alert(fields, settings_store)
        if error:
            if settings is None:
                return result("respond", pages.response_bad_request())
            return result("respond", pages.response_settings_page(
                settings=settings, alert_error=error, alert_editor=True,
                status_code=status,
            ))
        return result("respond", pages.response_settings_page(
            settings=updated, alert_saved=True
        ), renew_session_id=entry.encoded_id)
    if fields.get("alert_action") == "edit":
        from src.device.web.alert_route import edit_alert
        settings, updated, error, status = edit_alert(fields, settings_store)
        alert_id = fields.get("alert_id")
        if error:
            if settings is None:
                return result("respond", pages.response_bad_request())
            return result("respond", pages.response_settings_page(
                settings=settings, alert_error=error,
                editing_alert_id=alert_id, status_code=status,
            ))
        return result("respond", pages.response_settings_page(
            settings=updated, alert_saved=True
        ), renew_session_id=entry.encoded_id)
    if fields.get("alert_action") == "delete":
        from src.device.web.alert_route import delete_alert
        settings, updated, error, status = delete_alert(fields, settings_store)
        alert_id = fields.get("alert_id")
        if error:
            if settings is None:
                return result("respond", pages.response_bad_request())
            return result("respond", pages.response_settings_page(
                settings=settings, alert_error=error,
                editing_alert_id=alert_id, status_code=status,
            ))
        response = pages.response_settings_page(settings=updated, alert_saved=True)
        return result("respond", response.replace(b"Alert saved.", b"Alert deleted."),
                      renew_session_id=entry.encoded_id)
    password = fields.get("new_password", "")
    if not isinstance(password, str):
        password = str(password)
    if not validate_admin_password_field(password).ok:
        request.body = b""
        return result("respond", pages.response_bad_request())
    password_ba = bytearray(password.encode("utf-8"))
    request.body = b""
    return result("password_change_kdf", password=password_ba,
                  renew_session_id=entry.encoded_id)
