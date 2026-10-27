@echo off
setlocal
cd /d "%~dp0.."
set "LOG=%TEMP%\hermes-refresh.log"
echo [%DATE% %TIME%] refresh start >> "%LOG%"
".venv\Scripts\python.exe" manage.py refresh_news --limit 25 >> "%LOG%" 2>&1
echo [%DATE% %TIME%] refresh exit=%ERRORLEVEL% >> "%LOG%"
endlocal
