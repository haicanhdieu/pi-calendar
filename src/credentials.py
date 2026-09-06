"""Host-safe Wi-Fi credential soft-check (no secrets in config)."""


def credentials_valid():
    """
    Return True only when device-local secrets expose non-empty SSID and password.

    Missing ``secrets`` module, any import failure, or empty/whitespace values
    are invalid (soft fail for App composition).
    """
    try:
        import secrets as secrets_mod
    except Exception:
        return False
    try:
        ssid = getattr(secrets_mod, "WIFI_SSID", None) or ""
        password = getattr(secrets_mod, "WIFI_PASSWORD", None) or ""
        if not str(ssid).strip() or not str(password).strip():
            return False
        return True
    except Exception:
        return False
