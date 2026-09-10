"""Forward-only, bounded HTTP response sources."""


class ResponseSource:
    """A response made of immutable segments with one advancing cursor."""

    __slots__ = ("_parts", "total", "offset", "closed")

    def __init__(self, parts, total=None):
        self._parts = tuple(parts)
        self.total = (
            sum(len(part.encode("utf-8") if isinstance(part, str) else part)
                for part in self._parts)
            if total is None else int(total)
        )
        self.offset = 0
        self.closed = False

    @property
    def remaining(self):
        return max(0, self.total - self.offset)

    def read(self, max_bytes):
        """Return and consume at most ``max_bytes`` encoded response bytes."""
        if self.closed or self.offset >= self.total:
            return b""
        size = max(1, int(max_bytes))
        chunk = _response_chunk(self._parts, self.offset,
                                min(self.total, self.offset + size))
        self.offset += len(chunk)
        return chunk

    def read_at(self, start, stop):
        if self.closed:
            return b""
        return _response_chunk(self._parts, max(0, int(start)),
                               min(self.total, int(stop)))

    def close(self):
        self.closed = True
        self._parts = ()

    def __contains__(self, value):
        # Compatibility for host tests without materializing the response.
        if not isinstance(value, (bytes, bytearray)):
            return False
        return bytes(value) in b"".join(
            part.encode("utf-8") if isinstance(part, str) else part
            for part in self._parts
        )

    def __getattr__(self, name):
        """Keep byte-response inspection helpers working on host tests."""
        if name in ("split", "lower", "decode", "startswith", "endswith", "count"):
            payload = b"".join(
                part.encode("utf-8") if isinstance(part, str) else part
                for part in self._parts
            )
            return getattr(payload, name)
        raise AttributeError(name)

    def __getitem__(self, index):
        # Retain the old (parts, total) inspection shape for scan tests.
        if index == 0:
            return self._parts
        if index == 1:
            return self.total
        raise IndexError(index)


def _response_chunk(parts, start, stop):
    if stop <= start:
        return b""
    result = bytearray()
    offset = 0
    for part in parts:
        encoded = part.encode("utf-8") if isinstance(part, str) else part
        end = offset + len(encoded)
        if end > start and offset < stop:
            result.extend(encoded[max(0, start - offset):min(len(encoded), stop - offset)])
        offset = end
        if offset >= stop:
            break
    return bytes(result)


def _json_string(value):
    out = ['"']
    for char in str(value):
        code = ord(char)
        if char == '"': out.append('\\"')
        elif char == '\\': out.append('\\\\')
        elif char == '\n': out.append('\\n')
        elif char == '\r': out.append('\\r')
        elif code < 32: out.append('\\u%04x' % code)
        else: out.append(char)
    out.append('"')
    return ''.join(out)


def scan_response_stream(ssids, failed=False):
    body = ['{"error":"scan_failed"}' if failed else '{"ssids":[']
    if failed:
        header = ('HTTP/1.1 503 Service Unavailable\r\nContent-Type: application/json\r\n'
                  'Content-Length: {}\r\nConnection: close\r\n\r\n').format(len(body[0].encode('utf-8')))
        return ResponseSource((header,) + tuple(body))
    for index, value in enumerate(ssids):
        if index:
            body.append(',')
        body.append(_json_string(value))
    body.append(']}')
    body_length = sum(len(part.encode('utf-8')) for part in body)
    header = ('HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n'
              'Content-Length: {}\r\nConnection: close\r\n\r\n').format(body_length)
    parts = tuple([header] + body)
    return ResponseSource(parts, len(header.encode('utf-8')) + body_length)


def scan_response_chunk(response, start, stop):
    if isinstance(response, ResponseSource):
        return response.read_at(start, min(stop, start + 64))
    parts, total = response
    return _response_chunk(parts, start, min(stop, start + 64, total))
