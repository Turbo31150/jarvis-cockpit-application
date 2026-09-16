@echo off
rem tests.cmd — tests unitaires de la couche plateforme avec le Python Windows (.venv).
setlocal
set "RACINE=%~dp0..\..\.."
for %%I in ("%RACINE%") do set "RACINE=%%~fI"
cd /d "%RACINE%\cockpit"
set "PYTHONUTF8=1"
set "PYTHONPATH=%RACINE%\cockpit"
"%RACINE%\.venv\Scripts\python.exe" -m unittest tests_platform_compat -q %*
exit /b %ERRORLEVEL%
