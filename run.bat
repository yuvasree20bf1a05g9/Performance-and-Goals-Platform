@echo off
REM Double-click to set up and run PerformanceHub on Windows.
REM Optional: run.bat --profile starter   (small dataset, starts in seconds)
cd /d "%~dp0"
where python >nul 2>nul || (echo Python 3.10+ is required: https://www.python.org/downloads/ & pause & exit /b 1)
if not exist .venv (
  echo Creating virtual environment...
  python -m venv .venv || (pause & exit /b 1)
)
call .venv\Scripts\activate.bat
echo Installing requirements...
python -m pip install -q --upgrade pip
python -m pip install -q -r requirements.txt || (pause & exit /b 1)
python manage.py all --open %*
pause
