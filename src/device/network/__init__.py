"""Package exports for the network boundary.

Host-importable surface is limited to the pure mailbox protocol. Device worker
and proof harness must be imported explicitly so CPython/host paths never pull
``_thread`` (or optional network stubs) through this package root.
"""

from src.device.network.mailbox import (
    Mailbox,
    MailboxSaturationError,
    SyncCommand,
    SyncResult,
    result_is_expired,
    should_apply_result,
)

__all__ = [
    "Mailbox",
    "MailboxSaturationError",
    "SyncCommand",
    "SyncResult",
    "result_is_expired",
    "should_apply_result",
]
