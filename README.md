# BinHTTP/1.0 — HTTP in Binary
### Network Architecture Course Project

| Role | Name | GitHub | Track |
|------|------|--------|-------|
| Server | Jagrit | [@Jagrit3500](https://github.com/Jagrit3500) | Track 1 — `bserve` |
| Client | Partner | [@shashwat.24bcs10360](https://github.com/shashwat.24bcs10360) | Track 2 — `bcurl` |

---

## What We Built

**BinHTTP/1.0** is a custom binary HTTP protocol designed and implemented from scratch.
It carries full HTTP semantics — method, path, status, headers, body — in a compact
binary wire format inspired by HTTP/2.

The key design goals:
- **Fixed 9-byte frame header** (Length 24-bit / Type 8-bit / Flags 8-bit / StreamID 31-bit) — same layout as HTTP/2, same reasons
- **Static header name table** — 10 predefined header IDs (HPACK's indexed-name mechanism)
- **Length-prefixed literal headers** — for anything not in the table (HPACK's second mechanism)
- **Persistent TCP connection** — server keeps it open; client never reopens it
- **Forward-compatibility skip rule** — unknown frame types are silently skipped, making room for version 2

> *In pairs: one server, one client, and the only thing that crosses between you is the spec.*
> *A client that only works against your own server is an implementation, not a protocol.*

---

## Repository Layout

```
Jagrit_NetworkArchitecture_Project/
│
│  ── SHARED ───────────────────────────────────────────────────
├── spec.md                  # BinHTTP/1.0 protocol specification (2 pages)
├── protocol.py              # Shared frame encoder / decoder / hexdump library
├── hexdump_annotated.md     # Annotated wire dump of one complete exchange
│
│  ── TRACK 1: SERVER (Jagrit / @Jagrit3500) ──────────────────
├── server/
│   ├── bserve.py            # BinHTTP/1.0 TCP file server
│   ├── bserve.bat           # Windows launcher
│   └── www/
│       ├── index.html       # Default served file
│       └── about.html       # Second test file
│
│  ── TRACK 2: CLIENT (@shashwat.24bcs10360) ────────────────────────
└── client/
    ├── bcurl.py             # BinHTTP/1.0 client
    └── bcurl.bat            # Windows launcher
```

---

## How to Run

### Start the server (Track 1 — Jagrit)
```powershell
# Windows
python server\bserve.py ./server/www 9000

# With verbose frame hex-dumps
python server\bserve.py -v ./server/www 9000
```

### Run the client (Track 2 — shashwat.24bcs10360)
```powershell
# Windows — basic request
python client\bcurl.py localhost:9000/index.html

# With verbose frame hex-dumps
python client\bcurl.py -v localhost:9000/index.html
```

---

## Protocol Summary

### Frame Wire Format (9-byte header)

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
|                  Payload  (Length bytes)                     ...
+---------------------------------------------------------------+
```

| Field | Size | Reason |
|-------|------|--------|
| Length | 24-bit | Up to 16 MiB per frame — no 64-bit overhead |
| Type | 8-bit | 256 extension codes for future versions |
| Flags | 8-bit | Per-type semantic bits (reserved 0x00 for now) |
| StreamID | 31-bit | R-bit reserved; mirrors HTTP/2 for future multiplexing |

### Frame Types

| Code | Name | Direction |
|------|------|-----------|
| 0x00 | REQUEST | Client → Server |
| 0x01 | RESPONSE | Server → Client |
| other | *unknown — skip cleanly* | any |

### The One Rule You Cannot Skip

> A receiver meeting a frame type it does not know **MUST** read `Length` bytes and discard them silently, then continue.
> This is the only mechanism that makes room for a version 2.

---

## What We Hand In

| # | Deliverable | File |
|---|------------|------|
| 1 | Protocol specification — 2 pages, enough for a stranger | `spec.md` |
| 2 | Server implementation (Track 1 — Jagrit) | `server/bserve.py` |
| 2 | Client implementation (Track 2 — shashwat.24bcs10360) | `client/bcurl.py` |
| 2 | Shared protocol library | `protocol.py` |
| 3 | Annotated hexdump of one complete request/response | `hexdump_annotated.md` |

---

## Test Results

| Test | Command | Result |
|------|---------|--------|
| 200 OK | `python client\bcurl.py localhost:9000/index.html` | Body printed to stdout |
| Verbose frames | `python client\bcurl.py -v localhost:9000/index.html` | Full hex dump both ways |
| 404 Not Found | `python client\bcurl.py localhost:9000/missing.txt` | Exit code 1 |
| 400 Bad Request | Send malformed frame | Status 400 returned |
| Connection reuse | 3 requests on 1 socket | All 3 served, connection never closed |
| Unknown frame skip | Send type 0x42 then REQUEST | Server skips 0x42, serves 200 |
| Interoperability | Stranger's client (no shared code) | Got 200 from bserve |

---

*BinHTTP/1.0 — Jagrit (@Jagrit3500) & Partner (@shashwat.24bcs10360) — Network Architecture Course*
