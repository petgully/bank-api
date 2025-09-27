@echo off
echo ========================================
echo    Push Rules to Database
echo ========================================
echo.

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    pause
    exit /b 1
)

REM Install required packages
echo Installing required packages...
pip install -r requirements_db.txt

REM Load environment variables if .env file exists
if exist .env (
    echo Loading environment variables from .env file...
    for /f "usebackq tokens=1,2 delims==" %%a in (.env) do set %%a=%%b
)

REM Run the script
echo.
echo Running rules push script...
python push_rules_to_db.py

echo.
echo Script completed. Press any key to exit...
pause
