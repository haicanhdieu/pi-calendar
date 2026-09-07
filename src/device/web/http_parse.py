"""Bounded incremental HTTP/1.0–1.1 request parsing (pure; no sockets)."""

from src import config

STATE_LINE = "line"
STATE_HEADERS = "headers"
STATE_BODY = "body"
STATE_DONE = "done"
STATE_ERROR = "error"

ERR_MALFORMED = "malformed"
ERR_TOO_LARGE = "too_large"
ERR_UNSUPPORTED = "unsupported"


def html_escape(text):
    """Escape text for safe inclusion in HTML text/attribute contexts."""
    if text is None:
        return ""
    out = []
    for ch in str(text):
        if ch == "&":
            out.append("&amp;")
        elif ch == "<":
            out.append("&lt;")
        elif ch == ">":
            out.append("&gt;")
        elif ch == '"':
            out.append("&quot;")
        elif ch == "'":
            out.append("&#39;")
        else:
            out.append(ch)
    return "".join(out)


def parse_form_urlencoded(body):
    """
    Parse ``application/x-www-form-urlencoded`` body to a string dict.

    Duplicate keys keep the last value. Invalid percent-encoding yields
    ``None`` (caller treats as malformed). Values are UTF-8 decoded.
    """
    if body is None:
        return {}
    if isinstance(body, bytes):
        try:
            body = body.decode("utf-8")
        except Exception:
            return None
    if not isinstance(body, str):
        return None
    if body == "":
        return {}
    result = {}
    for part in body.split("&"):
        if not part:
            continue
        if "=" in part:
            key, raw_val = part.split("=", 1)
        else:
            key, raw_val = part, ""
        try:
            key = _percent_decode(key.replace("+", " "))
            val = _percent_decode(raw_val.replace("+", " "))
        except Exception:
            return None
        result[key] = val
    return result


def cookie_header_value(cookie_header, name):
    """
    Return the value of ``name`` from a raw ``Cookie`` header, or ``None``.

    Parses ``name=value`` pairs separated by ``;``. Matching is case-sensitive
    on the cookie name (checked-in ``pc_session``).
    """
    if not cookie_header or not name:
        return None
    if not isinstance(cookie_header, str):
        try:
            cookie_header = str(cookie_header)
        except Exception:
            return None
    target = str(name)
    for part in cookie_header.split(";"):
        piece = part.strip()
        if not piece:
            continue
        if "=" not in piece:
            continue
        key, value = piece.split("=", 1)
        if key.strip() == target:
            return value.strip()
    return None


def _percent_decode(text):
    out = bytearray()
    i = 0
    length = len(text)
    while i < length:
        ch = text[i]
        if ch == "%":
            if i + 2 >= length:
                raise ValueError("truncated percent")
            out.append(int(text[i + 1 : i + 3], 16))
            i += 3
        else:
            # Browsers normally percent-encode non-ASCII form values, but
            # accepting a literal UTF-8 character too keeps the decoder
            # compatible with small/mobile clients that do not.  ``append``
            # would reject code points above 255 and turn a valid SSID into a
            # generic 400 response.
            out.extend(ch.encode("utf-8"))
            i += 1
    return bytes(out).decode("utf-8")


class HttpRequest:
    """Completed HTTP request (method/path/headers/body)."""

    __slots__ = ("method", "path", "version", "headers", "body")

    def __init__(self, method, path, version, headers, body):
        self.method = method
        self.path = path
        self.version = version
        self.headers = headers
        self.body = body


class IncrementalHttpParser:
    """Feed recv bytes until one request completes or a fixed error fires."""

    def __init__(
        self,
        max_request_line=None,
        max_headers=None,
        max_body=None,
    ):
        self.max_request_line = (
            config.HTTP_MAX_REQUEST_LINE
            if max_request_line is None
            else int(max_request_line)
        )
        self.max_headers = (
            config.HTTP_MAX_HEADERS_BYTES
            if max_headers is None
            else int(max_headers)
        )
        self.max_body = (
            config.HTTP_MAX_BODY_BYTES if max_body is None else int(max_body)
        )
        self.state = STATE_LINE
        self.error = None
        self._buf = bytearray()
        self._headers_bytes = 0
        self.method = None
        self.path = None
        self.version = None
        self.headers = {}
        self._content_length = 0
        self.body = b""

    def feed(self, data):
        """
        Consume ``data`` bytes.

        Returns ``(request_or_None, error_or_None, consumed)``.
        """
        if self.state == STATE_ERROR:
            return None, self.error, 0
        if self.state == STATE_DONE:
            return self._as_request(), None, 0
        if not data:
            return None, None, 0

        consumed = 0
        view = memoryview(data) if not isinstance(data, memoryview) else data
        while consumed < len(view) and self.state not in (STATE_DONE, STATE_ERROR):
            if self.state == STATE_LINE:
                n = self._feed_line(view[consumed:])
                if n <= 0:
                    break
                consumed += n
            elif self.state == STATE_HEADERS:
                n = self._feed_headers(view[consumed:])
                if n <= 0:
                    break
                consumed += n
            elif self.state == STATE_BODY:
                n = self._feed_body(view[consumed:])
                if n <= 0:
                    break
                consumed += n
        if self.state == STATE_ERROR:
            return None, self.error, consumed
        if self.state == STATE_DONE:
            return self._as_request(), None, consumed
        return None, None, consumed

    def _fail(self, code):
        self.state = STATE_ERROR
        self.error = code
        return 0

    def _feed_line(self, data):
        for i, byte in enumerate(data):
            self._buf.append(byte)
            if len(self._buf) > self.max_request_line:
                self._fail(ERR_TOO_LARGE)
                return i + 1
            if len(self._buf) >= 2 and self._buf[-2:] == b"\r\n":
                line = bytes(self._buf[:-2])
                self._buf = bytearray()
                self._parse_request_line(line)
                return i + 1
        return len(data)

    def _parse_request_line(self, line):
        try:
            text = line.decode("ascii")
        except Exception:
            self._fail(ERR_MALFORMED)
            return
        parts = text.split(" ")
        if len(parts) != 3:
            self._fail(ERR_MALFORMED)
            return
        method, target, version = parts
        if version not in ("HTTP/1.0", "HTTP/1.1"):
            self._fail(ERR_UNSUPPORTED)
            return
        if not target.startswith("/"):
            self._fail(ERR_MALFORMED)
            return
        path = target.split("?", 1)[0]
        self.method = method.upper()
        self.path = path
        self.version = version
        self.state = STATE_HEADERS

    def _feed_headers(self, data):
        for i, byte in enumerate(data):
            self._buf.append(byte)
            self._headers_bytes += 1
            if self._headers_bytes > self.max_headers:
                self._fail(ERR_TOO_LARGE)
                return i + 1
            if len(self._buf) >= 2 and self._buf[-2:] == b"\r\n":
                line = bytes(self._buf[:-2])
                self._buf = bytearray()
                if line == b"":
                    self._headers_done()
                    return i + 1
                if self._parse_header_line(line) is False:
                    return i + 1
        return len(data)

    def _parse_header_line(self, line):
        try:
            text = line.decode("ascii")
        except Exception:
            self._fail(ERR_MALFORMED)
            return False
        if ":" not in text:
            self._fail(ERR_MALFORMED)
            return False
        name, value = text.split(":", 1)
        key = name.strip().lower()
        self.headers[key] = value.strip()
        return True

    def _headers_done(self):
        length_text = self.headers.get("content-length", "0")
        try:
            length = int(length_text)
        except Exception:
            self._fail(ERR_MALFORMED)
            return
        if length < 0:
            self._fail(ERR_MALFORMED)
            return
        if length > self.max_body:
            self._fail(ERR_TOO_LARGE)
            return
        self._content_length = length
        if length == 0:
            self.body = b""
            self.state = STATE_DONE
        else:
            self.state = STATE_BODY
            self._buf = bytearray()

    def _feed_body(self, data):
        need = self._content_length - len(self._buf)
        if need <= 0:
            self.body = bytes(self._buf)
            self.state = STATE_DONE
            return 0
        take = data[:need]
        self._buf.extend(take)
        if len(self._buf) >= self._content_length:
            self.body = bytes(self._buf[: self._content_length])
            self.state = STATE_DONE
        return len(take)

    def _as_request(self):
        return HttpRequest(
            self.method, self.path, self.version, dict(self.headers), self.body
        )
