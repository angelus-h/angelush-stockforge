@echo off
title StockForge Dashboard (Virtualenv)
cd /d "%~dp0"

echo ====================================================
echo             Angelus H. StockForge Studio
echo ====================================================

if not exist "dashboard\venv\Scripts\activate.bat" (
    echo [Setup] Creating virtual environment in dashboard\venv...
    python -m venv dashboard\venv
    if errorlevel 1 (
        echo [Error] Failed to create virtual environment. Ensure Python is installed.
        pause
        exit /b 1
    )
    call dashboard\venv\Scripts\activate.bat
    echo [Setup] Installing dependencies...
    python -m pip install --upgrade pip
    pip install -r dashboard\requirements.txt
) else (
    call dashboard\venv\Scripts\activate.bat
)

if "%1"=="--install" (
    echo [Setup] Updating dependencies...
    pip install -r dashboard\requirements.txt
)

echo Starting StockForge Dashboard...
streamlit run dashboard/app.py

pause