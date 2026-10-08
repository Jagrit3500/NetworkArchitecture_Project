# Makefile — BinHTTP/1.0 Project
# Works on Linux/macOS.  On Windows use the .bat wrappers directly.

.PHONY: all chmod run-server run-client test clean help

# ── Default target ────────────────────────────────────────────────────────────
all: chmod
	@echo ""
	@echo "BinHTTP/1.0 ready."
	@echo "  Server : ./bserve ./www 9000          (or: bserve.bat .\\www 9000)"
	@echo "  Client : ./bcurl -v localhost:9000/index.html"
	@echo ""

# ── Make scripts executable (Unix only) ─────────────────────────────────────
chmod:
	chmod +x bserve.py bcurl.py 2>/dev/null || true

# ── Run server in background ─────────────────────────────────────────────────
run-server:
	python bserve.py ./www 9000

# ── Run client ───────────────────────────────────────────────────────────────
run-client:
	python bcurl.py -v localhost:9000/index.html

# ── Quick smoke-test (requires server already running on port 9000) ──────────
test:
	@echo "--- Testing GET /index.html ---"
	python bcurl.py localhost:9000/index.html && echo "PASS" || echo "FAIL"
	@echo ""
	@echo "--- Testing GET /about.html ---"
	python bcurl.py localhost:9000/about.html && echo "PASS" || echo "FAIL"
	@echo ""
	@echo "--- Testing 404 ---"
	python bcurl.py localhost:9000/no-such-file.txt; \
	  [ $$? -eq 1 ] && echo "PASS (got 404, exit 1)" || echo "FAIL"

# ── Generate live hexdump (server must be running) ───────────────────────────
hexdump:
	python bcurl.py -v localhost:9000/index.html 2>&1 | head -60

# ── Clean compiled bytecode ───────────────────────────────────────────────────
clean:
	find . -name '*.pyc' -delete
	find . -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null || true

help:
	@grep -E '^[a-z_-]+:.*?##' Makefile | \
	  awk 'BEGIN {FS = ":.*?## "}; {printf "  %-18s %s\n", $$1, $$2}'
