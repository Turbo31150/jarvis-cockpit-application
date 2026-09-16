@echo off
rem driver.cmd — lance driver.py avec le Python Windows du depot (.venv). Memes arguments.
setlocal
set "RACINE=%~dp0..\..\.."
for %%I in ("%RACINE%") do set "RACINE=%%~fI"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
if not exist "%RACINE%\.venv\Scripts\python.exe" (echo [driver] .venv absent : lancez install.ps1 dans %RACINE% & exit /b 3)
"%RACINE%\.venv\Scripts\python.exe" -u "%~dp0driver.py" %*
exit /b %ERRORLEVEL%
