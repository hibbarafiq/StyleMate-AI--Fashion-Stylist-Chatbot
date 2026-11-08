@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title StyleMate AI Fashion Stylist

echo =============================================
echo          StyleMate AI Fashion Stylist
echo =============================================
echo.

if exist ".venv\Scripts\python.exe" goto venv_ready

echo [SETUP] Looking for an installed Python version...
set "PYTHON_CMD="

where py >nul 2>nul
if not errorlevel 1 goto use_py_launcher

where python >nul 2>nul
if not errorlevel 1 goto use_python_command

goto no_python


:use_py_launcher
echo [SETUP] Trying Python 3.12...
py -3.12 -m venv .venv >"setup_python.log" 2>&1
if exist ".venv\Scripts\python.exe" goto venv_ready

if exist ".venv" rmdir /s /q ".venv"

echo [SETUP] Trying Python 3.11...
py -3.11 -m venv .venv >"setup_python.log" 2>&1
if exist ".venv\Scripts\python.exe" goto venv_ready

if exist ".venv" rmdir /s /q ".venv"

echo [SETUP] Trying Python 3.13...
py -3.13 -m venv .venv >"setup_python.log" 2>&1
if exist ".venv\Scripts\python.exe" goto venv_ready

if exist ".venv" rmdir /s /q ".venv"

echo [SETUP] Trying Python 3.14...
py -3.14 -m venv .venv >"setup_python.log" 2>&1
if exist ".venv\Scripts\python.exe" goto venv_ready

if exist ".venv" rmdir /s /q ".venv"

echo [SETUP] Trying the default Python registered with the launcher...
py -m venv .venv >"setup_python.log" 2>&1
if exist ".venv\Scripts\python.exe" goto venv_ready

goto no_venv


:use_python_command
echo [SETUP] Trying the Python command available on PATH...
python -m venv .venv >"setup_python.log" 2>&1
if exist ".venv\Scripts\python.exe" goto venv_ready

goto no_venv


:venv_ready
echo [SETUP] Virtual environment ready.

call ".venv\Scripts\activate.bat"
if errorlevel 1 goto setup_error

echo.
echo [CHECK] Checking required Python packages...

python -c "import streamlit, pandas, sklearn, joblib, extra_streamlit_components" >nul 2>nul

if not errorlevel 1 goto start_app

echo.
echo [SETUP] One or more required packages are missing.
echo [SETUP] Installing packages from requirements.txt...
echo.

python -m pip install --upgrade pip
if errorlevel 1 goto setup_error

if not exist "requirements.txt" goto no_requirements

python -m pip install -r requirements.txt
if errorlevel 1 goto setup_error

echo.
echo [SETUP] Checking extra-streamlit-components...

python -c "import extra_streamlit_components" >nul 2>nul
if not errorlevel 1 goto verify_packages

python -m pip install extra-streamlit-components
if errorlevel 1 goto setup_error


:verify_packages
echo.
echo [CHECK] Verifying all required packages...

python -c "import streamlit, pandas, sklearn, joblib, extra_streamlit_components" >nul 2>nul
if errorlevel 1 goto package_error


:start_app
echo.
echo =============================================
echo       Starting StyleMate AI...
echo =============================================
echo.
echo Keep this window open while using the chatbot.
echo To stop the app, press Ctrl+C.
echo.

python -m streamlit run app.py

if errorlevel 1 goto run_error

exit /b 0


:no_requirements
echo.
echo ERROR: requirements.txt was not found.
echo Please make sure it exists in the project folder.
echo.
pause
exit /b 1


:package_error
echo.
echo ERROR: Required packages could not be imported.
echo Check the installation output above.
echo.
pause
exit /b 1


:no_python
echo.
echo ERROR: Python was not found on this computer.
echo Install Python from:
echo https://www.python.org/downloads/windows/
echo.
echo During installation, enable Add Python to PATH.
echo Then run this file again.
echo.
pause
exit /b 1


:no_venv
echo.
echo ERROR: Python was found, but the virtual environment
echo could not be created.
echo.
echo See setup_python.log for the detailed error.
echo.
pause
exit /b 1


:setup_error
echo.
echo ERROR: Setup or package installation failed.
echo Review the error displayed above.
echo Check your internet connection if installation failed.
echo.
pause
exit /b 1


:run_error
echo.
echo StyleMate AI stopped with an error.
echo Review the error displayed above.
echo.
pause
exit /b 1