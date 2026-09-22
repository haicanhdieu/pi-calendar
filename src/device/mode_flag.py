"""Config-mode handoff flag: one small file on the device filesystem.

Clock mode writes the flag and reboots; config mode deletes it as its very
first action. Deleting on *entry* rather than on exit is deliberate: a crash
anywhere inside config mode then returns the device to clock mode on the next
reset, instead of wedging it in a reboot loop with no way out.

The filesystem is the only medium available here. RTC scratch memory is not
portable to rp2, and the flag is written a handful of times in the device's
life, so flash wear is not a consideration.
"""

from src import config


def _path(path):
    return config.CONFIG_MODE_FLAG_PATH if path is None else path


def request_config_mode(path=None, open_fn=None):
    """Write the flag. Returns True when the caller may reboot into config."""
    opener = open if open_fn is None else open_fn
    try:
        handle = opener(_path(path), "w")
    except Exception:
        return False
    try:
        handle.write("1")
    except Exception:
        return False
    finally:
        try:
            handle.close()
        except Exception:
            pass
    return True


def consume_config_mode(path=None, open_fn=None, remove_fn=None):
    """Whether config mode was requested; the flag is cleared either way.

    Clearing unconditionally is what makes a config-mode crash self-healing,
    so the delete runs before the answer is returned, not after the session.
    """
    target = _path(path)
    opener = open if open_fn is None else open_fn
    requested = False
    try:
        handle = opener(target, "r")
    except Exception:
        handle = None
    if handle is not None:
        requested = True
        try:
            handle.close()
        except Exception:
            pass
    clear_config_mode(path=target, remove_fn=remove_fn)
    return requested


def clear_config_mode(path=None, remove_fn=None):
    """Delete the flag if present; a missing flag is not an error."""
    remover = remove_fn
    if remover is None:
        import os

        remover = os.remove
    try:
        remover(_path(path))
    except Exception:
        return False
    return True
