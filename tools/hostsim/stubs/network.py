"""Host stand-in for the Pico's ``network`` module.

The real CYW43 driver allocates its own buffers during association and DHCP,
which this stub does not model.  Heap figures from the simulation therefore
exclude Wi-Fi driver memory; treat them as a floor, not a ceiling.
"""

STA_IF = 0
AP_IF = 1

STAT_IDLE = 0
STAT_CONNECTING = 1
STAT_WRONG_PASSWORD = -3
STAT_NO_AP_FOUND = -2
STAT_CONNECT_FAIL = -1
STAT_GOT_IP = 3


class WLAN:
    def __init__(self, interface=STA_IF):
        self.interface = interface
        self._active = False
        self._connected = False

    def active(self, *args):
        if args:
            self._active = bool(args[0])
        return self._active

    def connect(self, *args, **kwargs):
        self._connected = True

    def disconnect(self):
        self._connected = False

    def isconnected(self):
        return self._connected

    def status(self, *args):
        return STAT_GOT_IP if self._connected else STAT_IDLE

    def ifconfig(self, *args):
        return ("192.168.1.32", "255.255.255.0", "192.168.1.1", "192.168.1.1")

    def config(self, *args, **kwargs):
        return b"simulated"

    def scan(self):
        return []
