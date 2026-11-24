@echo off
cd /d "%~dp0"
set "OUT=diagnose.txt"
echo Collecting info... please wait.
(
echo === Folder ===
cd
dir /b
echo.
echo === Python ===
py -3 --version 2>&1
python --version 2>&1
echo.
echo === Environment packages ===
if exist ".mcpenv\Scripts\python.exe" (
  ".mcpenv\Scripts\python.exe" --version
  ".mcpenv\Scripts\python.exe" -m pip list 2>&1 | findstr /i "streamlit fastmcp ollama"
  ".mcpenv\Scripts\python.exe" -c "import streamlit, fastmcp, ollama; print('imports OK')" 2>&1
) else (
  echo .mcpenv not created yet - run run.bat first
)
echo.
echo === Ollama ===
ollama list 2>&1
echo.
echo === Port 8000 ===
netstat -ano | findstr ":8000"
echo.
echo === mcp_server.log ===
if exist mcp_server.log type mcp_server.log
) > "%OUT%" 2>&1
echo Done. Open diagnose.txt and send me its contents.
notepad "%OUT%"
pause
