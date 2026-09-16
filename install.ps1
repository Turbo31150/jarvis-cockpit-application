# ============================================================================
# install.ps1 - Installation de JARVIS Cockpit comme application Windows.
#
# Usage (depuis la racine du depot, PowerShell 5.1 ou 7) :
#     powershell -ExecutionPolicy Bypass -File install.ps1
#     powershell -ExecutionPolicy Bypass -File install.ps1 -SansRaccourcis
#     powershell -ExecutionPolicy Bypass -File install.ps1 -Reinstaller
#
# Ce que fait le script (idempotent : relancable sans risque) :
#   1. choisit le meilleur Python disponible (C:\Python313, C:\Python311, py -3)
#   2. cree ou met a jour .venv puis pip install -r requirements.txt
#   3. cree %USERPROFILE%\jarvis\{logs,data,databases,board,cockpit}
#      (dossier de donnees de l'application = JARVIS_HOME)
#   4. fabrique icons\jarvis_cockpit.ico s'il manque (via icons\make_ico.py)
#   5. cree les raccourcis : Bureau "JARVIS Cockpit.lnk" et
#      Menu Demarrer\Programmes\JARVIS Cockpit\{GUI, Web :8600, TUI}.lnk
#
# Il ne touche NI au registre NI au PATH. Pas besoin d'etre administrateur.
# Fichier volontairement ASCII (pas d'accents) : PowerShell 5.1 lit les .ps1
# sans BOM en ANSI et deformerait les caracteres UTF-8.
# ============================================================================
[CmdletBinding()]
param(
    [switch]$SansRaccourcis,   # ne cree pas les .lnk
    [switch]$Reinstaller,      # supprime .venv et le recree
    [switch]$SansPip           # saute pip install (hors ligne)
)

$ErrorActionPreference = "Stop"
$Racine = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Racine

function Etape([string]$msg) { Write-Host "==> $msg" -ForegroundColor Cyan }
function Ok([string]$msg)    { Write-Host "    [OK] $msg" -ForegroundColor Green }
function Info([string]$msg)  { Write-Host "    $msg" }
function Avert([string]$msg) { Write-Host "    [!] $msg" -ForegroundColor Yellow }

Write-Host ""
Write-Host "JARVIS Cockpit - installation Windows" -ForegroundColor White
Write-Host "Racine : $Racine"
Write-Host ""

# ---------------------------------------------------------------------------
# 1. Python de base
# ---------------------------------------------------------------------------
Etape "Recherche d'un interpreteur Python"
$PythonBase = $null
foreach ($cand in @("C:\Python313\python.exe", "C:\Python311\python.exe")) {
    if (Test-Path $cand) { $PythonBase = $cand; break }
}
if (-not $PythonBase) {
    $py = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($py) {
        try {
            $chemin = & $py.Source -3 -c "import sys; print(sys.executable)" 2>$null
            if ($LASTEXITCODE -eq 0 -and $chemin -and (Test-Path $chemin.Trim())) {
                $PythonBase = $chemin.Trim()
            }
        } catch { }
    }
}
if (-not $PythonBase) {
    $p = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($p -and $p.Source -notlike "*WindowsApps*") { $PythonBase = $p.Source }
}
if (-not $PythonBase) {
    throw "Aucun Python 3 trouve (C:\Python313, C:\Python311, py -3). Installez Python 3.11+ depuis python.org."
}
$version = & $PythonBase -c "import sys; print('%d.%d.%d' % sys.version_info[:3])"
Ok "Python $version : $PythonBase"

# ---------------------------------------------------------------------------
# 2. Environnement virtuel
# ---------------------------------------------------------------------------
Etape "Environnement virtuel .venv"
$Venv     = Join-Path $Racine ".venv"
$VenvPy   = Join-Path $Venv "Scripts\python.exe"
$VenvPyw  = Join-Path $Venv "Scripts\pythonw.exe"
$VenvCfg  = Join-Path $Venv "pyvenv.cfg"

if ($Reinstaller -and (Test-Path $Venv)) {
    Info "Suppression de l'ancien .venv (-Reinstaller)"
    Remove-Item -Recurse -Force $Venv
}
$venvValide = (Test-Path $VenvPy) -and (Test-Path $VenvCfg)
if ($venvValide) {
    # Un .venv dont le Python de base a disparu (pyvenv.cfg pointe dans le vide)
    # se relance en boucle ; on le detecte et on le recree.
    try { & $VenvPy -c "import sys" | Out-Null; $venvValide = ($LASTEXITCODE -eq 0) } catch { $venvValide = $false }
    if (-not $venvValide) { Avert ".venv casse, recreation" ; Remove-Item -Recurse -Force $Venv }
}
if (-not $venvValide) {
    Info "Creation : $PythonBase -m venv .venv"
    & $PythonBase -m venv $Venv
    if ($LASTEXITCODE -ne 0) { throw "Echec de la creation du venv" }
    Ok ".venv cree"
} else {
    Ok ".venv deja present"
}
if (-not (Test-Path $VenvPyw)) { throw "pythonw.exe absent du venv : $VenvPyw" }

# ---------------------------------------------------------------------------
# 3. Dependances
# ---------------------------------------------------------------------------
Etape "Dependances Python (requirements.txt)"
if ($SansPip) {
    Avert "pip install saute (-SansPip)"
} else {
    # Pas de redirection 2>&1 : sous PS 5.1 avec ErrorActionPreference=Stop,
    # une simple ligne sur stderr (avertissement pip) deviendrait une erreur fatale.
    & $VenvPy -m pip install --upgrade pip --quiet --disable-pip-version-check
    & $VenvPy -m pip install -r (Join-Path $Racine "requirements.txt") --disable-pip-version-check
    if ($LASTEXITCODE -ne 0) { throw "pip install -r requirements.txt a echoue" }
    Ok "requirements.txt installe"
}
# Controle des imports critiques : mieux vaut echouer ici qu'au double-clic.
& $VenvPy -c "import PyQt6.QtWidgets, textual, psutil, requests; from PyQt6.QtCore import QT_VERSION_STR; print('Qt', QT_VERSION_STR)"
if ($LASTEXITCODE -ne 0) { throw "Import PyQt6/textual/psutil/requests impossible dans le venv" }
Ok "PyQt6, textual, psutil, requests importables"

# ---------------------------------------------------------------------------
# 4. Dossiers de donnees (JARVIS_HOME)
# ---------------------------------------------------------------------------
Etape "Dossiers de donnees"
$JarvisHome = $env:JARVIS_HOME
if (-not $JarvisHome) { $JarvisHome = Join-Path $env:USERPROFILE "jarvis" }
foreach ($sous in @("", "logs", "data", "databases", "board", "cockpit")) {
    $d = Join-Path $JarvisHome $sous
    if (-not (Test-Path $d)) { New-Item -ItemType Directory -Path $d | Out-Null; Info "cree  $d" }
}
Ok "JARVIS_HOME = $JarvisHome"

# ---------------------------------------------------------------------------
# 5. Icone .ico
# ---------------------------------------------------------------------------
Etape "Icone Windows"
$Ico = Join-Path $Racine "icons\jarvis_cockpit.ico"
$icoValide = (Test-Path $Ico) -and ((Get-Item $Ico).Length -gt 1024)
if (-not $icoValide) {
    Info "Fabrication via icons\make_ico.py"
    $env:QT_QPA_PLATFORM = "offscreen"
    & $VenvPy (Join-Path $Racine "icons\make_ico.py")
    Remove-Item Env:\QT_QPA_PLATFORM -ErrorAction SilentlyContinue
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path $Ico)) { throw "Echec de la fabrication de l'icone" }
}
try {
    Add-Type -AssemblyName System.Drawing
    $icone = New-Object System.Drawing.Icon($Ico)
    Ok ("jarvis_cockpit.ico valide ({0}x{1}, {2} octets)" -f $icone.Width, $icone.Height, (Get-Item $Ico).Length)
    $icone.Dispose()
} catch {
    Avert "Windows n'a pas pu lire l'icone : $($_.Exception.Message)"
}

# ---------------------------------------------------------------------------
# 6. Raccourcis
# ---------------------------------------------------------------------------
function Creer-Raccourci {
    param(
        [string]$Chemin,        # fichier .lnk a ecrire
        [string]$Cible,         # executable
        [string]$Arguments,
        [string]$Description
    )
    $shell = New-Object -ComObject WScript.Shell
    $lnk = $shell.CreateShortcut($Chemin)
    $lnk.TargetPath       = $Cible
    $lnk.Arguments        = $Arguments
    $lnk.WorkingDirectory = $Racine
    $lnk.IconLocation     = "$Ico,0"
    $lnk.Description      = $Description
    $lnk.WindowStyle      = 1
    $lnk.Save()
    [System.Runtime.InteropServices.Marshal]::ReleaseComObject($shell) | Out-Null
    Ok "raccourci : $Chemin"
}

if ($SansRaccourcis) {
    Etape "Raccourcis sautes (-SansRaccourcis)"
} else {
    Etape "Raccourcis"
    $Lanceur   = Join-Path $Racine "jarvis_cockpit_launcher.pyw"
    $Bureau    = [Environment]::GetFolderPath("Desktop")
    $MenuProg  = Join-Path ([Environment]::GetFolderPath("Programs")) "JARVIS Cockpit"
    if (-not (Test-Path $MenuProg)) { New-Item -ItemType Directory -Path $MenuProg | Out-Null }

    # GUI : pythonw.exe -> aucune fenetre console.
    Creer-Raccourci -Chemin (Join-Path $Bureau "JARVIS Cockpit.lnk") `
        -Cible $VenvPyw -Arguments "`"$Lanceur`"" `
        -Description "JARVIS Cockpit - application de bureau (PyQt6)"
    Creer-Raccourci -Chemin (Join-Path $MenuProg "JARVIS Cockpit.lnk") `
        -Cible $VenvPyw -Arguments "`"$Lanceur`"" `
        -Description "JARVIS Cockpit - application de bureau (PyQt6)"
    # Serveur web et TUI : python.exe (console visible, journaux a l'ecran).
    Creer-Raccourci -Chemin (Join-Path $MenuProg "JARVIS Cockpit Web (port 8600).lnk") `
        -Cible $VenvPy -Arguments "`"$Lanceur`" --web" `
        -Description "JARVIS Cockpit - serveur HTTP local sur http://127.0.0.1:8600"
    Creer-Raccourci -Chemin (Join-Path $MenuProg "JARVIS Cockpit TUI.lnk") `
        -Cible $VenvPy -Arguments "`"$Lanceur`" --tui" `
        -Description "JARVIS Cockpit - tableau de bord Textual en console"
    Creer-Raccourci -Chemin (Join-Path $MenuProg "JARVIS Cockpit (console de debogage).lnk") `
        -Cible (Join-Path $Racine "JARVIS-Cockpit.cmd") -Arguments "" `
        -Description "JARVIS Cockpit - lancement avec console visible (debogage)"
}

# ---------------------------------------------------------------------------
# Recapitulatif
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "Installation terminee." -ForegroundColor Green
Write-Host "  Lancer l'application : double-clic sur 'JARVIS Cockpit' (Bureau / menu Demarrer)"
Write-Host "  Console de debogage  : $Racine\JARVIS-Cockpit.cmd"
Write-Host "  Serveur web          : $Racine\JARVIS-Cockpit.cmd --web   (http://127.0.0.1:8600)"
Write-Host "  Journal des erreurs  : $JarvisHome\logs\cockpit-gui.log"
Write-Host "  Documentation        : $Racine\README-WINDOWS.md"
Write-Host ""
