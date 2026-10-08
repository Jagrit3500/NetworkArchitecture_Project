# BinHTTP/1.0 — Protocol Specification
### Jagrit — Network Architecture Course Project

---

## 1. Overview

**BinHTTP/1.0** is a binary, frame-based, request/response protocol that runs
over TCP.  It carries HTTP semantics (method, path, status, headers, body) in a
compact wire format inspired by HTTP/2.  A single TCP connection stays open for
multiple sequential request/response exchanges.

---

## 2. Frame Format

Every message is wrapped in a **frame**.  All multi-byte integers are
**big-endian unsigned**.

```
 0                   1                   2                   3
 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                       Length (24 bits)                        |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|    Type (8)   |   Flags (8)   |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|R|                Stream Identifier (31 bits)                  |
+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+
|                  Payload  (Length octets)                    ...
+---------------------------------------------------------------+
```

| Field     | Size    | Description |
|-----------|---------|-------------|
| Length    | 24 bits | Number of bytes in the payload. Max 16 777 215 bytes. |
| Type      | 8 bits  | Frame type code (see Section 3). |
| Flags     | 8 bits  | Type-specific flags. Currently 0x00 (reserved). |
| R         | 1 bit   | Reserved; MUST be sent as 0, ignored on receipt. |
| Stream ID | 31 bits | Logical stream identifier. Currently always 1. |
| Payload   | Length bytes | Type-dependent content (see Sections 4 and 5). |

**Field-width rationale** — HTTP/2 chose the same 24/8/8/31 split because:
- **24-bit length** avoids 64-bit arithmetic on every frame while still
  allowing single-frame file transfers up to 16 MiB.
- **8-bit type** provides 256 type codes — ample room for future extensions
  without wasting header bytes.
- **31-bit stream ID** (with 1 reserved bit) mirrors HTTP/2 and leaves the
  door open for multiplexing in a future version.

---

## 3. Frame Types

| Code   | Name     | Direction |
|--------|----------|-----------|
| 0x00   | REQUEST  | Client to Server |
| 0x01   | RESPONSE | Server to Client |
| other  | unknown  | any |

### Forward-Compatibility Rule (MANDATORY)

A receiver that encounters a frame Type it does not recognise MUST:
1. Read exactly Length bytes from the wire.
2. Discard them silently.
3. Continue reading the next frame.

A receiver MUST NOT close the connection on an unknown frame type.
This is the only mechanism that makes room for a version 2.

---

## 4. Header Encoding

Both REQUEST and RESPONSE payloads use the same header block format:

```
hdr_count  (1 byte)
for each header:
    name_id   (1 byte)
    [if name_id == 0xFF - literal name:]
        name_len  (2 bytes big-endian)
        name      (name_len UTF-8 bytes)
    value_len (2 bytes big-endian)
    value     (value_len UTF-8 bytes)
```

**Static name table** (HPACK first-two-mechanisms: indexed names + length-prefix):

| ID   | Name             | ID   | Name              |
|------|------------------|------|-------------------|
| 0x01 | Host             | 0x06 | Connection        |
| 0x02 | User-Agent       | 0x07 | Accept-Encoding   |
| 0x03 | Accept           | 0x08 | Cache-Control     |
| 0x04 | Content-Type     | 0x09 | Authorization     |
| 0x05 | Content-Length   | 0x0A | Accept-Language   |
| 0xFF | (literal name)   |      |                   |

---

## 5. Payload Formats

### 5.1 REQUEST Payload (Type = 0x00)

```
method    (1 byte)   0x00=GET  0x01=POST  0x02=HEAD
path_len  (2 bytes big-endian)
path      (path_len UTF-8 bytes, e.g. "/index.html")
[header block per Section 4]
```

A malformed REQUEST (missing fields, path_len overflow) MUST receive a
400 Bad Request RESPONSE. The connection remains open.

### 5.2 RESPONSE Payload (Type = 0x01)

```
status    (2 bytes big-endian)  e.g. 0x00C8 = 200
[header block per Section 4]
body      (remaining bytes)
```

---

## 6. Connection Semantics

**Server**: accepts one TCP connection, reads frames in a loop, replies,
and keeps the connection open indefinitely until the client closes it.
Returns 404 if the file is absent; 400 if the frame is malformed.

**Client**: opens exactly one TCP connection and never opens a second one.
Sends one REQUEST, reads frames (skipping unknowns) until it receives a
RESPONSE, writes the body to stdout, and exits non-zero on 4xx/5xx.

---

## 7. Status Codes

| Code | Meaning        |
|------|----------------|
| 200  | OK             |
| 400  | Bad Request    |
| 404  | Not Found      |

A client MUST exit non-zero (signal failure) on any status >= 400.

---

*BinHTTP/1.0 — Jagrit — Network Architecture Course*
