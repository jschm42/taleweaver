@echo off
REM TaleWeaver Admin Reset Script for Windows

cd /d "%~dp0.."

where python >nul 2>nul
if %ERRORLEVEL% equ 0 (
    python scripts\reset_admin.py %*
) else (
    echo Error: Python is not in your PATH.
    pause
)
