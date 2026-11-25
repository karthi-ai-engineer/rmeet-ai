@echo off
rem One command to run the demo. Usage:  run   |   run --no-browser   |   run --stop
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
    py -3 run.py %*
) else (
    python run.py %*
)
