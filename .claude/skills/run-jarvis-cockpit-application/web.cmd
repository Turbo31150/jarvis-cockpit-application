@echo off
rem web.cmd [port] — serveur HTTP/JSON du cockpit avec le Python Windows (.venv). Defaut 8600.
setlocal
set "RACINE=%~dp0..\..\.."
for %%I in ("%RACINE%") do set "RACINE=%%~fI"
cd /d "%RACINE%"
set "PYTHONUTF8=1"
if not "%~1"=="" set "COCKPIT_PORT=%~1"
"%RACINE%\.venv\Scripts\python.exe" -u jarvis_cockpit_launcher.pyw --web
