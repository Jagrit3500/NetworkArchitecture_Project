#!/usr/bin/env python3
"""
bserve — BinHTTP/1.0 File Server
==================================
Usage:
    python bserve.py [-v] <root_dir> <port>
    bserve.bat  [-v] <root_dir> <port>           (Windows)
    ./bserve    [-v] <root_dir> <port>            (Unix after chmod +x)

Options:
    -v   Verbose: hex-dump every frame sent and received.

Behaviour:
  • Listens for TCP connections on <port>.
  • Reads binary BinHTTP/1.0 frames (see protocol.py / spec.md).
  • Maps the requested path to a file under <root_dir>.
  • Replies with a RESPONSE frame containing status, headers, and body.
  • Returns 404 if the file is not found.
  • Returns 400 if the REQUEST frame is malformed.
  • Unknown frame types are skipped cleanly (read + discard payload).
  • Keeps the connection open for further requests.
"""

import os
import sys
import socket
import mimetypes
import threading

# ── Add both this dir and parent dir to sys.path ─────────────────────────────
# protocol.py lives at the repo root; bserve.py lives in server/
# so we add both so `import protocol` works regardless of cwd.
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)   # repo root where protocol.py lives
for _p in (_HERE, _ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from protocol import (
    read_frame, write_frame, build_raw_frame,
    decode_request, encode_response,
    TYPE_REQUEST, TYPE_RESPONSE,
    METHOD_HEAD,
    hexdump,
)


# ── Per-connection handler ────────────────────────────────────────────────────

def handle_client(conn, addr, root, verbose):
    """Serve one TCP connection until the client closes it."""
    tag = f'[bserve {addr[0]}:{addr[1]}]'
    print(f'{tag} connected')

    try:
        while True:
            # ── Read next frame ───────────────────────────────────────────
            try:
                ftype, flags, sid, payload = read_frame(conn)
            except EOFError:
                print(f'{tag} disconnected')
                break

            if verbose:
                raw = build_raw_frame(ftype, flags, sid, payload)
                print(f'{tag} >> RX frame type=0x{ftype:02X}  '
                      f'{len(payload)} payload bytes')
                print(hexdump(raw, prefix='    '))

            # ── Forward-compatibility: skip unknown frame types ───────────
            # MANDATORY: a receiver MUST skip any frame type it does not know.
            # The payload was already fully consumed by read_frame(), so we
            # simply continue to the next frame without closing the connection.
            if ftype != TYPE_REQUEST:
                print(f'{tag} unknown frame type 0x{ftype:02X} '
                      f'({len(payload)} bytes) — skipped')
                continue

            # ── Parse REQUEST ─────────────────────────────────────────────
            try:
                method_code, path, req_headers = decode_request(payload)
            except ValueError as exc:
                print(f'{tag} malformed REQUEST: {exc}')
                body = b'400 Bad Request'
                resp = encode_response(400,
                    [('Content-Type', 'text/plain'),
                     ('Content-Length', str(len(body)))],
                    body)
                write_frame(conn, TYPE_RESPONSE, resp, stream_id=sid)
                continue

            # ── Resolve path → file ───────────────────────────────────────
            clean = path.lstrip('/')
            if not clean:
                clean = 'index.html'

            full_path = os.path.normpath(os.path.join(root, clean))
            root_norm = os.path.normpath(root)

            # Security: path must stay inside root (no ../.. escapes)
            in_root = (
                full_path == root_norm
                or full_path.startswith(root_norm + os.sep)
            )

            if not in_root or not os.path.isfile(full_path):
                body = b'404 Not Found'
                resp = encode_response(404,
                    [('Content-Type', 'text/plain'),
                     ('Content-Length', str(len(body)))],
                    body)
                write_frame(conn, TYPE_RESPONSE, resp, stream_id=sid)
                print(f'{tag} 404 {path}')
                if verbose:
                    raw = build_raw_frame(TYPE_RESPONSE, 0, sid, resp)
                    print(f'{tag} << TX RESPONSE 404')
                    print(hexdump(raw, prefix='    '))
                continue

            # ── Read file & send 200 response ─────────────────────────────
            with open(full_path, 'rb') as fh:
                file_body = fh.read()

            mime, _ = mimetypes.guess_type(full_path)
            if not mime:
                mime = 'application/octet-stream'

            resp_headers = [
                ('Content-Type',   mime),
                ('Content-Length', str(len(file_body))),
            ]
            # HEAD: send headers only, no body
            send_body = b'' if method_code == METHOD_HEAD else file_body

            resp = encode_response(200, resp_headers, send_body)
            write_frame(conn, TYPE_RESPONSE, resp, stream_id=sid)
            print(f'{tag} 200 {path} ({len(file_body)} bytes)')

            if verbose:
                raw = build_raw_frame(TYPE_RESPONSE, 0, sid, resp)
                print(f'{tag} << TX RESPONSE 200  '
                      f'{len(resp)} payload bytes')
                print(hexdump(raw, prefix='    '))

    finally:
        conn.close()
        print(f'{tag} connection closed')


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    argv = sys.argv[1:]
    verbose = '-v' in argv
    pos = [a for a in argv if not a.startswith('-')]

    if len(pos) < 2:
        prog = os.path.basename(sys.argv[0])
        print(f'Usage: {prog} [-v] <root_dir> <port>', file=sys.stderr)
        sys.exit(1)

    root = os.path.abspath(pos[0])
    try:
        port = int(pos[1])
    except ValueError:
        print(f'Error: port must be an integer, got {pos[1]!r}', file=sys.stderr)
        sys.exit(1)

    if not os.path.isdir(root):
        print(f'Error: {root!r} is not a directory', file=sys.stderr)
        sys.exit(1)

    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(('', port))
    srv.listen(64)

    print(f'[bserve] Listening on 0.0.0.0:{port}  root={root}')
    if verbose:
        print('[bserve] Verbose mode ON — frame hex-dumps enabled')

    try:
        while True:
            conn, addr = srv.accept()
            t = threading.Thread(
                target=handle_client,
                args=(conn, addr, root, verbose),
                daemon=True,
            )
            t.start()
    except KeyboardInterrupt:
        print('\n[bserve] Shutting down.')
    finally:
        srv.close()


if __name__ == '__main__':
    main()
