@echo off
setlocal
cd /d "%~dp0"

where py >nul 2>nul
if %ERRORLEVEL%==0 (
    py -3 install.py
) else (
    where python >nul 2>nul
    if %ERRORLEVEL%==0 (
        python install.py
    ) else (
        echo ERROR: Python was not found. Install Python 3.11+ from https://www.python.org/downloads/
        echo IMPORTANT: check "Add python.exe to PATH" during setup.
        pause
        exit /b 1
    )
)

if %ERRORLEVEL% neq 0 (
    echo.
    echo Installation failed - see the messages above.
)

pause
