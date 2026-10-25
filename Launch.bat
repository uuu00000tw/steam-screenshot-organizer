@echo off
cd /d "%~dp0"
set "PYW=%LocalAppData%\Programs\Python\Python310\pythonw.exe"
set "PY=%LocalAppData%\Programs\Python\Python310\python.exe"
if not exist "%PYW%" set "PYW=pythonw"
if not exist "%PY%" set "PY=python"
start "" "%PYW%" "%~dp0gui.py"
