@echo off
REM TaleWeaver Admin Reset Script for Windows
setlocal EnableDelayedExpansion

cd /d "%~dp0.."

REM Use the project's environment (the system Python lacks the dependencies):
REM Poetry first, then a local .venv, then the system Python.
REM !ERRORLEVEL! (delayed expansion) passes the real exit code on from inside the blocks.
where poetry >nul 2>nul
if not errorlevel 1 (
    poetry env info -p >nul 2>nul
    if not errorlevel 1 (
        poetry run python scripts\reset_admin.py %*
        exit /b !ERRORLEVEL!
    )
)

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" scripts\reset_admin.py %*
    exit /b !ERRORLEVEL!
)

where python >nul 2>nul
if not errorlevel 1 (
    python scripts\reset_admin.py %*
    exit /b !ERRORLEVEL!
)

echo Error: Python is not in your PATH.
pause
exit /b 1
