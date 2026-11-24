@echo off
setlocal
cd /d "%~dp0"
title Local MCP Chatbot
set "VENV=.mcpenv"
set "PY=%VENV%\Scripts\python.exe"
set STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

echo ================================================
echo  Local LLM + MCP Chatbot
echo ================================================

rem --- Reuse the environment only if it really works (ignores any old/moved .venv) ---
if exist "%PY%" (
    "%PY%" -c "import streamlit, fastmcp, ollama" >nul 2>&1
    if not errorlevel 1 goto :run
    echo Existing environment is broken - rebuilding it...
    rmdir /s /q "%VENV%"
)

rem --- Find Python ---
set "SYSPY="
py -3 --version >nul 2>&1 && set "SYSPY=py -3"
if not defined SYSPY (
    python --version >nul 2>&1 && set "SYSPY=python"
)
if not defined SYSPY (
    echo.
    echo Python was not found. Install Python 3.12 from https://www.python.org/downloads/
    echo and tick "Add python.exe to PATH" during setup. Then run this file again.
    goto :fail
)
echo Using Python: %SYSPY%

echo.
echo [1/3] Creating environment...
%SYSPY% -m venv "%VENV%" || goto :fail
echo [2/3] Upgrading pip...
"%PY%" -m pip install --upgrade pip || goto :fail
echo [3/3] Installing packages (needs internet, a few minutes)...
"%PY%" -m pip install -r requirements.txt || goto :fail

:run
echo.
echo Starting chatbot at http://localhost:8501  (keep this window open)
echo Make sure the Ollama app is running.
"%PY%" -m streamlit run app.py
echo.
echo Streamlit stopped. If this was an error, copy the text above.
pause
exit /b 0

:fail
echo.
echo ===== SETUP FAILED. Copy ALL the text above and send it for help. =====
pause
exit /b 1
