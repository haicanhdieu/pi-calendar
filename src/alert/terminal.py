"""Terminal alert configuration transition."""


def disable_one_time_alerts(members, settings, store, log):
    ids = {item.get("id") for item in members if not item.get("weekdays")}
    if not ids:
        return settings
    current = store.load() if store is not None else settings
    if not isinstance(current, dict):
        return settings
    next_alerts = []
    changed = False
    for alert in current.get("alerts", []):
        item = dict(alert)
        if item.get("id") in ids and item.get("enabled"):
            item["enabled"] = False
            changed = True
        next_alerts.append(item)
    if not changed:
        return settings
    if store is None:
        current["alerts"] = next_alerts
        return current
    try:
        return store.commit(
            wifi_ssid=current["wifi_ssid"],
            wifi_password=current["wifi_password"],
            admin_salt_hex=current["admin_salt"],
            admin_verifier_hex=current["admin_verifier"],
            color_scheme=current["color_scheme"],
            alerts=next_alerts,
            postpone_delay_minutes=current.get("postpone_delay_minutes", 10),
        )
    except Exception as exc:
        log("alert_fail persist %s" % getattr(exc, "code", "commit"))
        return settings
