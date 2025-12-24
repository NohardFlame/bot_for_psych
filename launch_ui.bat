@echo off
setlocal enabledelayedexpansion

echo ========================================
echo Bot UI Launcher
echo ========================================
echo.

REM Check if Python is installed and get version
echo [1/5] Checking Python installation...
python --version >nul 2>&1
if errorlevel 1 (
    echo Python is not installed or not in PATH.
    goto :install_python
)

REM Get Python version and parse it
for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYTHON_VERSION=%%i
echo Found Python version: %PYTHON_VERSION%

REM Parse version numbers (format: 3.14.0)
for /f "tokens=1,2 delims=." %%a in ("%PYTHON_VERSION%") do (
    set MAJOR=%%a
    set MINOR=%%b
)

REM Check if version is less than 3.14
if %MAJOR% LSS 3 (
    echo Python version is too old (major version %MAJOR%).
    goto :install_python
)

if %MAJOR% EQU 3 (
    if %MINOR% LSS 14 (
        echo Python version %PYTHON_VERSION% is less than 3.14.
        goto :install_python
    )
)

echo Python version check passed!
goto :check_venv

:install_python
echo.
echo [2/5] Installing Python 3.14+ via winget...
winget install Python.Python.3.14 --silent --accept-package-agreements --accept-source-agreements
if errorlevel 1 (
    echo Failed to install Python via winget. Please install Python 3.14+ manually.
    echo Download from: https://www.python.org/downloads/
    pause
    exit /b 1
)

REM Refresh PATH to include newly installed Python
echo Refreshing PATH...
call refreshenv >nul 2>&1
if errorlevel 1 (
    echo Note: You may need to restart the terminal or add Python to PATH manually.
)

REM Verify installation
python --version >nul 2>&1
if errorlevel 1 (
    echo Python installation completed but not found in PATH.
    echo Please restart the terminal and run this script again.
    pause
    exit /b 1
)

for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYTHON_VERSION=%%i
echo Python %PYTHON_VERSION% installed successfully!

:check_venv
echo.
echo [3/5] Checking virtual environment...
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

:install_deps
echo.
echo [4/5] Installing dependencies...
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

:launch_ui
echo.
echo [5/5] Launching UI...
echo.
.venv\Scripts\python.exe run_ui.py
if errorlevel 1 (
    echo.
    echo Failed to launch UI.
    pause
    exit /b 1
)

endlocal

