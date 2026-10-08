#!/usr/bin/env python3
"""
bcurl — BinHTTP/1.0 Client
============================
Usage:
    python bcurl.py [-v] <host>:<port>/<path>
    bcurl.bat  [-v] <host>:<port>/<path>         (Windows)
    ./bcurl    [-v] <host>:<port>/<path>          (Unix after chmod +x)

Options:
    -v   Verbose: hex-dump every frame sent and received (to stderr).

Behaviour:
  • Opens exactly ONE TCP connection (never a second one).
  • Builds and sends one BinHTTP/1.0 REQUEST frame.
  • Reads RESPONSE frames; unknown frame types are skipped cleanly.
  • Writes the response body to stdout.
  • Exits non-zero (1) on 4xx or 5xx status codes.
  • Exits non-zero (2) on connection or parse errors.
"""

import os
import sys
import socket

# ── Add both this dir and parent dir to sys.path ─────────────────────────────
# protocol.py lives at the repo root; bcurl.py lives in client/
# so we add both so `import protocol` works regardless of cwd.
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)   # repo root where protocol.py lives
for _p in (_HERE, _ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from protocol import (
    read_frame, write_frame, build_raw_frame,
    encode_request, decode_response,
    TYPE_REQUEST, TYPE_RESPONSE,
    METHOD_GET,
    hexdump,
)


def parse_url(url):
    """
    Parse  host:port/path  or  host:port  into (host, port, path).
    Default port 9000, default path '/'.
    """
    if '/' in url:
        hostport, rest = url.split('/', 1)
        path = '/' + rest
    else:
        hostport = url
        path = '/'

    if ':' in hostport:
        host, port_str = hostport.rsplit(':', 1)
        port = int(port_str)
    else:
        host = hostport
        port = 9000

    return host, port, path


def eprint(*args, **kwargs):
    """Print to stderr (verbose output must not pollute stdout/body)."""
    print(*args, file=sys.stderr, **kwargs)


def main():
    argv = sys.argv[1:]
    verbose = '-v' in argv
    pos = [a for a in argv if not a.startswith('-')]

    if not pos:
        prog = os.path.basename(sys.argv[0])
        eprint(f'Usage: {prog} [-v] <host>:<port>/<path>')
        sys.exit(2)

    try:
        host, port, path = parse_url(pos[0])
    except ValueError as exc:
        eprint(f'Error parsing URL: {exc}')
        sys.exit(2)

    # ── Build REQUEST frame payload ────────────────────────────────────────
    req_headers = [
        ('Host',            f'{host}:{port}'),
        ('User-Agent',      'bcurl/1.0'),
        ('Accept',          '*/*'),
    ]
    payload   = encode_request(METHOD_GET, path, req_headers)
    stream_id = 1

    # ── Open exactly ONE TCP connection ────────────────────────────────────
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((host, port))
    except OSError as exc:
        eprint(f'Connection failed: {exc}')
        sys.exit(2)

    # ── Send REQUEST ───────────────────────────────────────────────────────
    if verbose:
        raw = build_raw_frame(TYPE_REQUEST, 0, stream_id, payload)
        eprint(f'>> REQUEST  {len(payload)} payload bytes  '
               f'GET {path}  →  {host}:{port}')
        eprint(hexdump(raw, prefix='   '))
        eprint()

    try:
        write_frame(sock, TYPE_REQUEST, payload, stream_id=stream_id)
    except OSError as exc:
        eprint(f'Send error: {exc}')
        sock.close()
        sys.exit(2)

    # ── Read frames until we get TYPE_RESPONSE ─────────────────────────────
    # (Unknown intermediate frames are skipped cleanly — forward-compat rule)
    exit_code = 0
    try:
        while True:
            try:
                ftype, flags, sid, resp_payload = read_frame(sock)
            except EOFError as exc:
                eprint(f'Error: server closed connection before response: {exc}')
                exit_code = 2
                break

            if verbose:
                raw = build_raw_frame(ftype, flags, sid, resp_payload)
                eprint(f'<< frame type=0x{ftype:02X}  {len(resp_payload)} payload bytes')
                eprint(hexdump(raw, prefix='   '))
                eprint()

            # Forward-compatibility: skip any frame type we don't recognise.
            if ftype != TYPE_RESPONSE:
                if verbose:
                    eprint(f'   [skip] unknown frame type 0x{ftype:02X}')
                continue

            # ── Parse RESPONSE ─────────────────────────────────────────────
            try:
                status, resp_headers, body = decode_response(resp_payload)
            except ValueError as exc:
                eprint(f'Malformed RESPONSE: {exc}')
                exit_code = 2
                break

            if verbose:
                eprint(f'   Status : {status}')
                for name, value in resp_headers:
                    eprint(f'   {name}: {value}')
                eprint()

            # ── Write body to stdout ───────────────────────────────────────
            sys.stdout.buffer.write(body)
            sys.stdout.buffer.flush()

            # ── Exit non-zero on 4xx / 5xx ─────────────────────────────────
            if status >= 400:
                eprint(f'HTTP error {status}')
                exit_code = 1

            break   # done – never open a second connection

    finally:
        sock.close()

    sys.exit(exit_code)


if __name__ == '__main__':
    main()
