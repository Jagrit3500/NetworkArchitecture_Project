@echo off
REM  bserve.bat — Windows launcher for the BinHTTP/1.0 server
REM  Usage:  bserve.bat [-v] <root_dir> <port>
REM  Example: bserve.bat ./www 9000
python "%~dp0bserve.py" %*
