# Annotated Hexdump — Complete BinHTTP/1.0 Exchange
### `./bcurl -v localhost:9000/index.html`

All bytes are live-captured from the actual bserve/bcurl implementation.
File served: `www/index.html` (63 bytes).

---

## REQUEST Frame (59 bytes wire total)

```
Offset  Hex dump (16 bytes/row)                           ASCII
──────────────────────────────────────────────────────────────────
0000    00 00 32 00 00 00 00 00  01 00 00 0b 2f 69 6e 64  ..2......../ind
0010    65 78 2e 68 74 6d 6c 03  01 00 0e 6c 6f 63 61 6c  ex.html....local
0020    68 6f 73 74 3a 39 30 30  30 02 00 09 62 63 75 72  host:9000...bcur
0030    6c 2f 31 2e 30 03 00 03  2a 2f 2a                 l/1.0...*/*
```

### Byte-by-byte annotation

```
── FRAME HEADER (bytes 0x00–0x08, 9 bytes) ──────────────────────
00 00 32   Length = 50  (0x32)   payload bytes that follow
00         Type   = 0x00         REQUEST
00         Flags  = 0x00         (none defined)
00 00 00   }
01         }  Stream ID = 1      (R-bit=0, stream 1)

── REQUEST PAYLOAD (bytes 0x09–0x3A, 50 bytes) ──────────────────

── Method (1 byte) ──────────────────────────────────────────────
[0x09] 00  Method = 0x00 = GET

── Path (2-byte length + string) ────────────────────────────────
[0x0A] 00 0b  path_len = 11
[0x0C] 2f 69 6e 64 65 78 2e 68 74 6d 6c   "/index.html"

── Header block ─────────────────────────────────────────────────
[0x17] 03  hdr_count = 3  (three headers follow)

  Header 1 — Host
  [0x18] 01        name_id = 0x01  → "Host"   (static table)
  [0x19] 00 0e     value_len = 14
  [0x1B] 6c 6f 63 61 6c 68 6f 73 74 3a 39 30 30 30
                   value = "localhost:9000"

  Header 2 — User-Agent
  [0x29] 02        name_id = 0x02  → "User-Agent"
  [0x2A] 00 09     value_len = 9
  [0x2C] 62 63 75 72 6c 2f 31 2e 30
                   value = "bcurl/1.0"

  Header 3 — Accept
  [0x35] 03        name_id = 0x03  → "Accept"
  [0x36] 00 03     value_len = 3
  [0x38] 2a 2f 2a  value = "*/*"
```

---

## RESPONSE Frame (92 bytes wire total)

```
Offset  Hex dump (16 bytes/row)                           ASCII
──────────────────────────────────────────────────────────────────
0000    00 00 53 01 00 00 00 00  01 00 c8 02 04 00 09 74  ..S.........t
0010    65 78 74 2f 68 74 6d 6c  05 00 02 36 33 3c 21 44  ext/html...63<!D
0020    4f 43 54 59 50 45 20 68  74 6d 6c 3e 0a 3c 68 74  OCTYPE html>.<ht
0030    6d 6c 3e 3c 62 6f 64 79  3e 3c 68 31 3e 42 69 6e  ml><body><h1>Bin
0040    48 54 54 50 2f 31 2e 30  3c 2f 68 31 3e 3c 2f 62  HTTP/1.0</h1></b
0050    6f 64 79 3e 3c 2f 68 74  6d 6c 3e 0a              ody></html>.
```

### Byte-by-byte annotation

```
── FRAME HEADER (bytes 0x00–0x08, 9 bytes) ──────────────────────
00 00 53   Length = 83  (0x53)   payload bytes that follow
01         Type   = 0x01         RESPONSE
00         Flags  = 0x00         (none)
00 00 00   }
01         }  Stream ID = 1      (mirrors the request stream)

── RESPONSE PAYLOAD (bytes 0x09–0x5B, 83 bytes) ─────────────────

── Status code (2 bytes) ─────────────────────────────────────────
[0x09] 00 c8  Status = 200  (0x00C8)  OK

── Header block ──────────────────────────────────────────────────
[0x0B] 02  hdr_count = 2

  Header 1 — Content-Type
  [0x0C] 04        name_id = 0x04  → "Content-Type"
  [0x0D] 00 09     value_len = 9
  [0x0F] 74 65 78 74 2f 68 74 6d 6c
                   value = "text/html"

  Header 2 — Content-Length
  [0x18] 05        name_id = 0x05  → "Content-Length"
  [0x19] 00 02     value_len = 2
  [0x1B] 36 33     value = "63"

── Body (63 bytes, remainder of payload) ─────────────────────────
[0x1D]  3c 21 44 4f 43 54 59 50 45 20 68 74 6d 6c 3e  "<!DOCTYPE html>"
[0x2C]  0a                                              "\n"
[0x2D]  3c 68 74 6d 6c 3e 3c 62 6f 64 79 3e            "<html><body>"
[0x39]  3c 68 31 3e 42 69 6e 48 54 54 50 2f 31 2e 30   "<h1>BinHTTP/1.0"
[0x48]  3c 2f 68 31 3e 3c 2f 62 6f 64 79 3e            "</h1></body>"
[0x54]  3c 2f 68 74 6d 6c 3e 0a                        "</html>\n"
```

---

## Counts at a Glance

| Item                 | Value |
|----------------------|-------|
| Request frame bytes  | 59    |
| Request payload      | 50    |
| Response frame bytes | 92    |
| Response payload     | 83    |
| Body bytes           | 63    |
| Headers in request   | 3     |
| Headers in response  | 2     |

---

## Forward-Compatibility Demonstration

If the server inserts an unknown frame type 0x42 (66-byte payload) between
the RESPONSE and the next exchange, the client reads the 9-byte header,
sees Type=0x42 (unrecognised), reads and discards 66 payload bytes, then
continues — the connection is NOT dropped.  This is the mandatory skip rule.

```
00 00 42 42 00 00 00 00 01  [66 payload bytes discarded]
└────── Length=66 ─────┘
        └── Type=0x42 (unknown) → skip cleanly
```

---

*If you cannot annotate your own bytes, the spec is not finished.*
*These bytes were captured from bserve.py / bcurl.py using `-v` mode.*
