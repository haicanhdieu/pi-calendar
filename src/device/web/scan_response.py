"""Lazy, low-allocation JSON response for setup Wi-Fi scans."""


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


def scan_response_stream(ssids):
    body = ['{"ssids":[']
    for index, value in enumerate(ssids):
        if index:
            body.append(',')
        body.append(_json_string(value))
    body.append(']}')
    body_length = sum(len(part.encode('utf-8')) for part in body)
    header = ('HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n'
              'Content-Length: {}\r\nConnection: close\r\n\r\n').format(body_length)
    parts = tuple([header] + body)
    return parts, len(header.encode('utf-8')) + body_length


def scan_response_chunk(response, start, stop):
    parts, total = response
    if stop <= start:
        return b''
    stop = min(stop, start + 64, total)
    result = bytearray()
    offset = 0
    for part in parts:
        encoded = part.encode('utf-8')
        end = offset + len(encoded)
        if end > start and offset < stop:
            result.extend(encoded[max(0, start - offset):min(len(encoded), stop - offset)])
        offset = end
        if offset >= stop:
            break
    return bytes(result)
