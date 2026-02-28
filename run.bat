@echo off
REM Nifty Paper Trading System - Windows Startup Script

echo ========================================
echo  Nifty Paper Trading System
echo ========================================

REM Check if venv exists
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
)

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat

REM Install/update requirements
echo Installing dependencies...
pip install -r requirements.txt > nul 2>&1

REM Run the app
echo.
echo ========================================
echo  Starting Flask Backend...
echo ========================================
echo.
echo Open browser: http://localhost:5000
echo.

python app.py

pause
