@echo off
REM KIRA Frontend Startup Script for Windows

echo.
echo 4  KIRA Frontend Startup
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found
    exit /b 1
)

REM Create virtual environment if needed
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
)

REM Activate venv
call venv\Scripts\activate.bat

REM Install requirements
echo Installing dependencies...
pip install -q -r requirements.txt

REM Check for .env
if not exist ".env" (
    echo Creating .env from template...
    if exist ".env.template" (
        copy .env.template .env
        echo .env created. Please review and adjust if needed.
    )
)

REM Start Streamlit
echo.
echo Starting KIRA Command Center...
echo Dashboard: http://localhost:8501
echo.

streamlit run app.py --logger.level=info --client.showErrorDetails=false

pause
