@echo off
REM  bcurl.bat — Windows launcher for the BinHTTP/1.0 client
REM  Usage:  bcurl.bat [-v] <host>:<port>/<path>
REM  Example: bcurl.bat -v localhost:9000/index.html
python "%~dp0bcurl.py" %*
