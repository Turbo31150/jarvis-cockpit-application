@echo off
rem ===========================================================================
rem JARVIS-Cockpit.cmd - Lanceur CONSOLE de JARVIS Cockpit (Windows).
rem
rem Meme logique que jarvis_cockpit_launcher.pyw, mais avec une console
rem visible : utile pour le debogage. La fenetre reste ouverte en cas
rem d'erreur pour que le message ne disparaisse pas.
rem
rem   JARVIS-Cockpit.cmd          application PyQt6
rem   JARVIS-Cockpit.cmd --web    serveur HTTP :8600
rem   JARVIS-Cockpit.cmd --tui    tableau de bord Textual (dans cette console)
rem ===========================================================================
setlocal
set "RACINE=%~dp0"
if "%RACINE:~-1%"=="\" set "RACINE=%RACINE:~0,-1%"
cd /d "%RACINE%"

if "%JARVIS_HOME%"=="" set "JARVIS_HOME=%USERPROFILE%\jarvis"
set "PYTHONPATH=%RACINE%\cockpit;%PYTHONPATH%"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
chcp 65001 >nul 2>&1

set "PY=%RACINE%\.venv\Scripts\python.exe"
if not exist "%PY%" (
    echo [JARVIS] Environnement .venv absent : lancez d'abord
    echo     powershell -ExecutionPolicy Bypass -File "%RACINE%\install.ps1"
    goto :erreur
)

echo [JARVIS] Racine   : %RACINE%
echo [JARVIS] Donnees  : %JARVIS_HOME%
echo [JARVIS] Journal  : %JARVIS_HOME%\logs\cockpit-gui.log
echo [JARVIS] Python   : %PY%
echo [JARVIS] Arguments: %*
echo.

"%PY%" "%RACINE%\jarvis_cockpit_launcher.pyw" %*
set "CODE=%ERRORLEVEL%"
if not "%CODE%"=="0" (
    echo.
    echo [JARVIS] Termine avec le code %CODE%. Voir le journal ci-dessus.
    goto :erreur
)
endlocal
exit /b 0

:erreur
echo.
pause
endlocal
exit /b 1
