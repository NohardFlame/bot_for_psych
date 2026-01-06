@echo off
setlocal enabledelayedexpansion

echo ========================================
echo Bot UI Launcher
echo ========================================
echo.

REM Check virtual environment
echo [1/3] Checking virtual environment...
if not exist ".venv" (
    echo Virtual environment not found. Creating .venv...
    python -m venv .venv
    if errorlevel 1 (
        echo Failed to create virtual environment.
        pause
        exit /b 1
    )
    echo Virtual environment created successfully!
) else (
    echo Virtual environment already exists.
)

REM Install dependencies
echo.
echo [2/3] Installing dependencies...
if not exist "requirements.txt" (
    echo Warning: requirements.txt not found. Skipping dependency installation.
    goto :launch_ui
)

.venv\Scripts\python.exe -m pip install --upgrade pip >nul 2>&1
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 (
    echo Failed to install dependencies.
    pause
    exit /b 1
)
echo Dependencies installed successfully!

REM Launch UI
:launch_ui
echo.
echo [3/3] Launching UI...
echo.
.venv\Scripts\python.exe run_ui.py
if errorlevel 1 (
    echo.
    echo Failed to launch UI.
    pause
    exit /b 1
)

endlocal



