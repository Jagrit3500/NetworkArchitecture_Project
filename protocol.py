"""
BinHTTP/1.0  -  Shared Protocol Library
========================================
Frame wire format  (9-byte fixed header, inspired by HTTP/2):

    +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
    |              Length (24 bits, big-endian)      |
    +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
    |  Type (8)  |  Flags (8) |
    +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
    |R|                  Stream Identifier (31 bits)                 |
    +=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+
    |                  Frame Payload  (Length bytes)                ...
    +---------------------------------------------------------------+

Field choices (all big-endian, unsigned):
  Length   24-bit  → max 16 MiB payload; matches HTTP/2 reason: fits any
                      reasonable file transfer without 64-bit overhead.
  Type      8-bit  → 256 possible frame types; plenty for v2 extensions.
  Flags     8-bit  → per-type semantic bits (currently unused, reserved 0x00).
  StreamID 32-bit  → top bit reserved (must be 0); 31-bit range mirrors
                      HTTP/2; allows request/response multiplexing later.
  HTTP/2 chose exactly 24/8/8/31 for the same reasons.

MANDATORY RULE (forward-compatibility):
  A receiver MUST skip any frame whose Type it does not recognise.
  It reads Length bytes from the wire, discards them, and continues.
  Failing to skip would make every extension a breaking change.
"""

import struct

# ── Frame constants ──────────────────────────────────────────────────────────

FRAME_HEADER_SIZE = 9      # bytes

# Known frame types
TYPE_REQUEST  = 0x00
TYPE_RESPONSE = 0x01
# Any other type code: skip cleanly (see read_frame).

# Request method codes
METHOD_GET  = 0x00
METHOD_POST = 0x01
METHOD_HEAD = 0x02

METHOD_NAMES = {
    METHOD_GET:  'GET',
    METHOD_POST: 'POST',
    METHOD_HEAD: 'HEAD',
}

# ── Static header-name table (HPACK-inspired, first 10 names) ───────────────
# Numbered 0x01..0x0A so that 0x00 is always invalid and 0xFF is literal.
HEADER_IDS = {
    0x01: 'Host',
    0x02: 'User-Agent',
    0x03: 'Accept',
    0x04: 'Content-Type',
    0x05: 'Content-Length',
    0x06: 'Connection',
    0x07: 'Accept-Encoding',
    0x08: 'Cache-Control',
    0x09: 'Authorization',
    0x0A: 'Accept-Language',
}

HEADER_NAMES_TO_IDS = {v.lower(): k for k, v in HEADER_IDS.items()}

LITERAL_HEADER = 0xFF   # sentinel: followed by 2-byte name-len + name bytes


# ── I/O helpers ──────────────────────────────────────────────────────────────

def read_exactly(sock, n):
    """Read exactly *n* bytes from *sock*.  Raises EOFError on close."""
    buf = bytearray()
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise EOFError(
                f'Connection closed; wanted {n} bytes, got {len(buf)}'
            )
        buf += chunk
    return bytes(buf)


# ── Frame I/O ────────────────────────────────────────────────────────────────

def read_frame(sock):
    """
    Read one complete frame from *sock*.

    Returns (frame_type, flags, stream_id, payload).

    IMPORTANT: The payload is ALWAYS fully consumed from the wire, even for
    unknown frame types.  Callers MUST check frame_type and skip gracefully
    if the type is not recognised – this is the forward-compatibility contract.
    """
    raw_hdr = read_exactly(sock, FRAME_HEADER_SIZE)

    length    = (raw_hdr[0] << 16) | (raw_hdr[1] << 8) | raw_hdr[2]
    ftype     = raw_hdr[3]
    flags     = raw_hdr[4]
    stream_id = struct.unpack('>I', raw_hdr[5:9])[0] & 0x7FFF_FFFF  # mask R bit

    payload = read_exactly(sock, length) if length else b''
    return ftype, flags, stream_id, payload


def write_frame(sock, frame_type, payload, *, flags=0, stream_id=1):
    """Encode and send one frame synchronously."""
    n = len(payload)
    if n > 0xFF_FFFF:
        raise ValueError(f'Payload too large: {n} bytes')

    header = bytes([
        (n >> 16) & 0xFF,
        (n >>  8) & 0xFF,
         n        & 0xFF,
        frame_type & 0xFF,
        flags & 0xFF,
    ]) + struct.pack('>I', stream_id & 0x7FFF_FFFF)

    sock.sendall(header + payload)


def build_raw_frame(frame_type, flags, stream_id, payload):
    """Return the wire bytes for a frame (header + payload) without sending."""
    n = len(payload)
    header = bytes([
        (n >> 16) & 0xFF,
        (n >>  8) & 0xFF,
         n        & 0xFF,
        frame_type & 0xFF,
        flags & 0xFF,
    ]) + struct.pack('>I', stream_id & 0x7FFF_FFFF)
    return header + payload


# ── Header encoding/decoding ─────────────────────────────────────────────────

def encode_headers(headers):
    """
    Encode a list of (name, value) pairs into the wire format:

        hdr_count (1 byte)
        for each header:
            name_id  (1 byte)     0x01-0x0A → predefined name
                                  0xFF       → literal name follows
            [if literal]
                name_len (2 bytes big-endian)
                name     (name_len bytes UTF-8)
            value_len (2 bytes big-endian)
            value     (value_len bytes UTF-8)

    HPACK mechanisms used: indexed name (IDs 1-10) + length-prefix.
    """
    parts = [bytes([len(headers)])]
    for name, value in headers:
        name_lower = name.lower()
        val_bytes  = value.encode() if isinstance(value, str) else bytes(value)

        if name_lower in HEADER_NAMES_TO_IDS:
            parts.append(bytes([HEADER_NAMES_TO_IDS[name_lower]]))
        else:
            name_bytes = name.encode()
            parts.append(bytes([LITERAL_HEADER]))
            parts.append(struct.pack('>H', len(name_bytes)))
            parts.append(name_bytes)

        parts.append(struct.pack('>H', len(val_bytes)))
        parts.append(val_bytes)

    return b''.join(parts)


def decode_headers(data, offset):
    """
    Decode headers from *data* starting at *offset*.
    Returns ([(name, value), ...], new_offset).
    Raises ValueError on malformed input.
    """
    if offset >= len(data):
        raise ValueError('Missing header count byte')

    count  = data[offset]; offset += 1
    result = []

    for i in range(count):
        if offset >= len(data):
            raise ValueError(f'Header {i}: truncated at name_id')

        name_id = data[offset]; offset += 1

        if name_id == LITERAL_HEADER:
            if offset + 2 > len(data):
                raise ValueError(f'Header {i}: truncated name_len')
            name_len = struct.unpack('>H', data[offset:offset+2])[0]; offset += 2
            if offset + name_len > len(data):
                raise ValueError(f'Header {i}: name truncated')
            name = data[offset:offset+name_len].decode(); offset += name_len
        elif name_id in HEADER_IDS:
            name = HEADER_IDS[name_id]
        else:
            raise ValueError(f'Header {i}: unknown name ID 0x{name_id:02X}')

        if offset + 2 > len(data):
            raise ValueError(f'Header {i}: truncated value_len')
        val_len = struct.unpack('>H', data[offset:offset+2])[0]; offset += 2
        if offset + val_len > len(data):
            raise ValueError(f'Header {i}: value truncated')
        value = data[offset:offset+val_len].decode(errors='replace'); offset += val_len

        result.append((name, value))

    return result, offset


# ── Payload encoding/decoding ─────────────────────────────────────────────────

def encode_request(method_code, path, headers):
    """
    Build a REQUEST frame payload:
        method   (1 byte)
        path_len (2 bytes big-endian)
        path     (path_len bytes UTF-8)
        headers  (encode_headers format)
    """
    path_bytes = path.encode()
    return b''.join([
        bytes([method_code & 0xFF]),
        struct.pack('>H', len(path_bytes)),
        path_bytes,
        encode_headers(headers),
    ])


def decode_request(payload):
    """
    Parse a REQUEST payload.
    Returns (method_code, path, [(name, value), ...]).
    Raises ValueError if the frame is malformed.
    """
    if len(payload) < 4:
        raise ValueError('REQUEST payload too short')

    method_code = payload[0]
    path_len    = struct.unpack('>H', payload[1:3])[0]

    if 3 + path_len > len(payload):
        raise ValueError('Path length exceeds payload')

    path    = payload[3:3 + path_len].decode()
    offset  = 3 + path_len
    headers, _ = decode_headers(payload, offset)

    return method_code, path, headers


def encode_response(status_code, headers, body=b''):
    """
    Build a RESPONSE frame payload:
        status   (2 bytes big-endian)
        headers  (encode_headers format)
        body     (remaining bytes)
    """
    if isinstance(body, str):
        body = body.encode()
    return b''.join([
        struct.pack('>H', status_code),
        encode_headers(headers),
        body,
    ])


def decode_response(payload):
    """
    Parse a RESPONSE payload.
    Returns (status_code, [(name, value), ...], body_bytes).
    Raises ValueError if malformed.
    """
    if len(payload) < 3:
        raise ValueError('RESPONSE payload too short')

    status  = struct.unpack('>H', payload[0:2])[0]
    headers, offset = decode_headers(payload, 2)
    body    = payload[offset:]

    return status, headers, body


# ── Hex-dump utility ──────────────────────────────────────────────────────────

def hexdump(data, prefix=''):
    """
    Return a classic xxd-style hex dump string.

    Each line: <offset>  <hex bytes × 16>  |<ASCII>|
    """
    lines = []
    for i in range(0, len(data), 16):
        chunk    = data[i:i + 16]
        hex_part = ' '.join(f'{b:02x}' for b in chunk)
        asc_part = ''.join(chr(b) if 0x20 <= b < 0x7F else '.' for b in chunk)
        lines.append(f'{prefix}{i:04x}  {hex_part:<47}  |{asc_part}|')
    return '\n'.join(lines)
