@echo off
setlocal
cd /d "%~dp0"
py main.py
if errorlevel 1 (
  echo.
  echo OpenFix could not start. Check that Python and requirements are installed.
  echo Run: py -m pip install -r requirements.txt
  echo.
  pause
)
endlocal
