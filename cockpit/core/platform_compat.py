#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JARVIS COCKPIT — COUCHE DE COMPATIBILITÉ PLATEFORME (Linux rig ⇄ Windows 11)
============================================================================
Point unique où le cockpit décide « comment faire ça ici » : lancer un shell,
ouvrir un terminal, trouver un exécutable, tuer un arbre de processus, lire la
RAM/CPU/GPU, connaître le dossier Bureau… Tout le reste de l'application
importe ce module (``from core.platform_compat import …`` depuis les onglets et
les lanceurs, ``from .platform_compat import …`` depuis ``core/``) et ne teste
plus jamais ``sys.platform`` en direct.

Règles de conception (à respecter par tout ajout) :
  • STDLIB UNIQUEMENT à l'import — jamais ``core.config`` (config.py doit
    pouvoir importer ce module sans cycle) ; ``psutil`` est chargé
    paresseusement et son absence est tolérée partout.
  • Le chemin Linux reproduit le comportement HISTORIQUE du rig (gnome-terminal,
    tmux, loginctl, xdg-open, /proc…) : aucune régression sur la machine
    « mining ». Les adaptations Windows sont TOUTES derrière ``IS_WINDOWS``.
  • Aucun helper « d'action » ne lève : on rend None / False / un dict de stub
    (``unavailable``) avec un message français lisible. Les slots Qt et les
    routes HTTP peuvent donc appeler sans try/except.
  • Sous Windows, tout sous-processus console passe ``CREATE_NO_WINDOW`` (pas de
    console qui clignote sous pythonw.exe) et décode en UTF-8 ``errors='replace'``
    (la console est en cp850/cp1252 : ``text=True`` nu produit du mojibake ou
    lève UnicodeDecodeError sur l'accentué).
  • ``bash`` nu est INTERDIT sous Windows : ``shutil.which('bash')`` rend
    ``C:\\WINDOWS\\system32\\bash.EXE``, le lanceur WSL (démarrage à froid de
    plusieurs secondes, chemins C:\\ invalides). On ne prend que Git bash.
  • ``python3`` nu est INTERDIT sous Windows : alias Microsoft Store, pas le
    venv. Toujours ``python_exe()`` (= ``sys.executable``).

Tests : ``cockpit/tests_platform_compat.py`` (exécutable sur les deux OS).
"""

from __future__ import annotations

import csv
import functools
import getpass
import importlib
import importlib.util
import json
import os
import re
import shlex
import shutil
import signal
import socket
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import traceback
import uuid
import webbrowser
from types import SimpleNamespace

# ═══════════════════════════════════════════════════════════════════════════
#  CONSTANTES DE PLATEFORME
# ═══════════════════════════════════════════════════════════════════════════

IS_WINDOWS: bool = (sys.platform == "win32")
IS_LINUX: bool = sys.platform.startswith("linux")
IS_MAC: bool = (sys.platform == "darwin")


def _detect_wsl() -> bool:
    if not IS_LINUX:
        return False
    try:
        with open("/proc/version", "r", encoding="utf-8", errors="ignore") as fh:
            return "microsoft" in fh.read().lower()
    except OSError:
        return False


IS_WSL: bool = _detect_wsl()
PLATFORM_NAME: str = "windows" if IS_WINDOWS else ("wsl" if IS_WSL else ("linux" if IS_LINUX else sys.platform))


def is_windows() -> bool:
    """Forme fonction de IS_WINDOWS (pour les modules qui préfèrent un appel)."""
    return IS_WINDOWS


# creationflags Windows (0 partout ailleurs : ``creationflags=NO_WINDOW`` est
# toujours légal sous Linux, subprocess l'ignore).
NO_WINDOW: int = getattr(subprocess, "CREATE_NO_WINDOW", 0) if IS_WINDOWS else 0
_NEW_CONSOLE: int = getattr(subprocess, "CREATE_NEW_CONSOLE", 0) if IS_WINDOWS else 0
_NEW_GROUP: int = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) if IS_WINDOWS else 0
_DETACHED: int = getattr(subprocess, "DETACHED_PROCESS", 0) if IS_WINDOWS else 0

# Chemins de base — MÊME logique que core/config.py (qui ne peut pas être
# importé d'ici) : racine portable > JARVIS_HOME > ~/jarvis. Sous Windows
# ``expanduser('~')`` vaut %USERPROFILE%, donc ~/jarvis == %USERPROFILE%\\jarvis.
HOME: str = os.path.expanduser("~")
JARVIS_DIR: str = (os.environ.get("JARVIS_COCKPIT_ROOT")
                   or os.environ.get("JARVIS_HOME")
                   or os.path.join(HOME, "jarvis"))
LOGS_DIR_DEFAULT: str = os.path.join(JARVIS_DIR, "logs")

# Extensions reconnues comme lanceurs par le scan du Bureau / menus.
LAUNCHER_EXTS: tuple[str, ...] = (
    (".lnk", ".url", ".exe", ".bat", ".cmd", ".ps1", ".sh") if IS_WINDOWS
    else (".desktop", ".sh"))

# Outils qui n'ont AUCUN équivalent transparent sous Windows : which() rend
# None pour eux plutôt qu'un binaire Git/WSL au comportement surprenant.
LINUX_ONLY_TOOLS: frozenset[str] = frozenset({
    "tmux", "gnome-terminal", "x-terminal-emulator", "xterm", "xdg-open",
    "xdg-user-dir", "systemctl", "loginctl", "journalctl", "notify-send",
    "arecord", "pgrep", "pkill", "lsblk", "lsusb", "ip", "free", "xdotool",
    "gsettings", "dconf", "wmctrl", "lumen", "flo", "ttx", "moisson",
})

# Table des emplacements Windows connus (variables d'environnement acceptées).
_WIN_CANDIDATES: dict[str, tuple[str, ...]] = {
    "bash": (r"%ProgramFiles%\Git\bin\bash.exe", r"C:\Program Files\Git\bin\bash.exe",
             r"%ProgramFiles%\Git\usr\bin\bash.exe", r"C:\Program Files\Git\usr\bin\bash.exe",
             r"%ProgramW6432%\Git\bin\bash.exe", r"%LOCALAPPDATA%\Programs\Git\bin\bash.exe"),
    "sh": (r"%ProgramFiles%\Git\bin\sh.exe", r"C:\Program Files\Git\bin\sh.exe",
           r"%ProgramFiles%\Git\usr\bin\sh.exe"),
    "git": (r"%ProgramFiles%\Git\cmd\git.exe", r"C:\Program Files\Git\cmd\git.exe",
            r"%LOCALAPPDATA%\Programs\Git\cmd\git.exe"),
    "nvidia-smi": (r"%SystemRoot%\System32\nvidia-smi.exe", r"C:\Windows\System32\nvidia-smi.exe",
                   r"%ProgramFiles%\NVIDIA Corporation\NVSMI\nvidia-smi.exe"),
    "tailscale": (r"%ProgramFiles%\Tailscale\tailscale.exe", r"C:\Program Files\Tailscale\tailscale.exe"),
    "wt": (r"%LOCALAPPDATA%\Microsoft\WindowsApps\wt.exe",),
    "ollama": (r"%LOCALAPPDATA%\Programs\Ollama\ollama.exe", r"%ProgramFiles%\Ollama\ollama.exe"),
    "lms": (r"%USERPROFILE%\.lmstudio\bin\lms.exe",
            r"%ProgramFiles%\LM Studio\resources\app\.webpack\lms.exe",
            r"C:\Program Files\LM Studio\resources\app\.webpack\lms.exe"),
    "lmstudio": (r"%ProgramFiles%\LM Studio\LM Studio.exe", r"C:\Program Files\LM Studio\LM Studio.exe",
                 r"%LOCALAPPDATA%\Programs\LM Studio\LM Studio.exe",
                 r"%LOCALAPPDATA%\LM-Studio\LM Studio.exe"),
    "claude": (r"%USERPROFILE%\.local\bin\claude.exe", r"%APPDATA%\npm\claude.cmd"),
    "agy": (r"%LOCALAPPDATA%\agy\bin\agy.exe", r"%LOCALAPPDATA%\Programs\agy\agy.exe"),
    "browseros": (r"%LOCALAPPDATA%\Programs\BrowserOS\BrowserOS.exe",
                  r"%ProgramFiles%\BrowserOS\BrowserOS.exe"),
    "claude-desktop": (r"%LOCALAPPDATA%\AnthropicClaude\claude.exe",
                       r"%LOCALAPPDATA%\Programs\Claude\Claude.exe"),
    "chrome": (r"%ProgramFiles%\Google\Chrome\Application\chrome.exe",
               r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe",
               r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
    "msedge": (r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe",
               r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"),
    "ssh": (r"%SystemRoot%\System32\OpenSSH\ssh.exe", r"%ProgramFiles%\Git\usr\bin\ssh.exe"),
    "docker": (r"%ProgramFiles%\Docker\Docker\resources\bin\docker.exe",),
    "sqlite3": (r"%ProgramFiles%\Git\usr\bin\sqlite3.exe", r"%ChocolateyInstall%\bin\sqlite3.exe"),
    "ffmpeg": (r"%ChocolateyInstall%\bin\ffmpeg.exe", r"%ProgramData%\chocolatey\bin\ffmpeg.exe"),
    "pwsh": (r"%ProgramFiles%\PowerShell\7\pwsh.exe", r"%LOCALAPPDATA%\Microsoft\WindowsApps\pwsh.exe"),
    "powershell": (r"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe",),
    "wsl": (r"%SystemRoot%\System32\wsl.exe",),
    "code": (r"%LOCALAPPDATA%\Programs\Microsoft VS Code\bin\code.cmd",
             r"%ProgramFiles%\Microsoft VS Code\bin\code.cmd"),
}

# Dossiers Windows explorés en plus du PATH par which() (variantes .exe/.cmd/.bat).
_WIN_EXTRA_DIRS: tuple[str, ...] = (
    r"%ProgramFiles%\Git\cmd", r"%ProgramFiles%\Git\bin", r"%ProgramFiles%\Tailscale",
    r"%LOCALAPPDATA%\Programs\Ollama", r"%ProgramFiles%\LM Studio",
    r"%USERPROFILE%\.lmstudio\bin", r"%SystemRoot%\System32", r"%USERPROFILE%\.local\bin",
    r"%APPDATA%\npm", r"%ChocolateyInstall%\bin", r"%ProgramData%\chocolatey\bin",
    r"%LOCALAPPDATA%\agy\bin",
)

_PATHEXT_DEFAULT = (".exe", ".cmd", ".bat", ".com")


# ═══════════════════════════════════════════════════════════════════════════
#  IMPORTS OPTIONNELS / MODULES POSIX
# ═══════════════════════════════════════════════════════════════════════════

def import_optional(name: str):
    """Importe un module s'il existe, sinon None (jamais d'exception)."""
    try:
        return importlib.import_module(name)
    except Exception:
        return None


def posix_module(name: str):
    """``pty`` / ``fcntl`` / ``termios`` / ``pwd`` / ``grp`` / ``tty`` / ``resource``
    importés paresseusement ; None sous Windows (où ``import pty`` lève
    ModuleNotFoundError: termios). À utiliser au lieu d'un import module-level."""
    if IS_WINDOWS:
        return None
    return import_optional(name)


def posix_modules() -> SimpleNamespace:
    """SimpleNamespace(pty, fcntl, termios, pwd, grp, tty, resource) — chaque
    attribut vaut le module ou None."""
    names = ("pty", "fcntl", "termios", "pwd", "grp", "tty", "resource")
    return SimpleNamespace(**{n: posix_module(n) for n in names})


@functools.lru_cache(maxsize=1)
def _psutil():
    return import_optional("psutil")


def has_psutil() -> bool:
    return _psutil() is not None


# ═══════════════════════════════════════════════════════════════════════════
#  CHEMINS
# ═══════════════════════════════════════════════════════════════════════════

def tmp_dir() -> str:
    """Dossier temporaire natif (tempfile.gettempdir())."""
    return tempfile.gettempdir()


def cockpit_root() -> str:
    """Dossier ``cockpit/`` du dépôt (parent de ``core/``) — repli quand
    JARVIS_DIR ne contient pas le dépôt (icônes, hardware.json, web/)."""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def repo_root() -> str:
    """Racine du dépôt git (parent de ``cockpit/``)."""
    return os.path.dirname(cockpit_root())


def jarvis_path(*parts: str, must_exist: bool = False) -> str | None:
    """``os.path.join(JARVIS_DIR, *parts)`` avec séparateurs natifs ; si
    ``must_exist`` et que le chemin n'existe pas → None (l'onglet affiche
    « script indisponible » au lieu de lancer une commande vouée à l'échec)."""
    p = os.path.join(JARVIS_DIR, *parts)
    if must_exist and not os.path.exists(p):
        return None
    return p


def _expand(p: str) -> str:
    return os.path.expanduser(os.path.expandvars(p))


def runtime_dir() -> str:
    """Répertoire runtime de session : Linux → $XDG_RUNTIME_DIR ou /run/user/<uid> ;
    Windows → %LOCALAPPDATA%\\Temp (ou tempfile.gettempdir()). Ne touche jamais
    os.getuid() sous Windows (AttributeError)."""
    if IS_WINDOWS:
        base = os.environ.get("LOCALAPPDATA")
        if base:
            cand = os.path.join(base, "Temp")
            if os.path.isdir(cand):
                return cand
        return tmp_dir()
    xdg = os.environ.get("XDG_RUNTIME_DIR")
    if xdg:
        return xdg
    try:
        return f"/run/user/{os.getuid()}"
    except AttributeError:
        return tmp_dir()


def _win_known_folder(folder_guid: str) -> str | None:
    """SHGetKnownFolderPath via ctypes (gère la redirection OneDrive du Bureau)."""
    if not IS_WINDOWS:
        return None
    try:
        import ctypes
        from ctypes import wintypes

        class GUID(ctypes.Structure):
            _fields_ = [("Data1", wintypes.DWORD), ("Data2", wintypes.WORD),
                        ("Data3", wintypes.WORD), ("Data4", wintypes.BYTE * 8)]

        def _guid(s: str) -> GUID:
            s = s.strip("{}")
            parts = s.split("-")
            g = GUID()
            g.Data1 = int(parts[0], 16)
            g.Data2 = int(parts[1], 16)
            g.Data3 = int(parts[2], 16)
            tail = bytes.fromhex(parts[3] + parts[4])
            for i, b in enumerate(tail):
                g.Data4[i] = b
            return g

        shell32 = ctypes.windll.shell32
        ole32 = ctypes.windll.ole32
        path_ptr = ctypes.c_wchar_p()
        guid = _guid(folder_guid)
        hr = shell32.SHGetKnownFolderPath(ctypes.byref(guid), 0, None, ctypes.byref(path_ptr))
        if hr != 0:
            return None
        try:
            return path_ptr.value
        finally:
            ole32.CoTaskMemFree(path_ptr)
    except Exception:
        return None


_FOLDERID_DESKTOP = "{B4BFCC3A-DB2C-424C-B029-7FE99A87C641}"


def _win_registry_desktop() -> str | None:
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders") as k:
            val, _ = winreg.QueryValueEx(k, "Desktop")
            return os.path.expandvars(val)
    except Exception:
        return None


def desktop_dir() -> str:
    """Dossier Bureau, séparateurs natifs.

    Windows : SHGetKnownFolderPath(FOLDERID_Desktop) → registre User Shell
    Folders → %USERPROFILE%\\Desktop. Linux : ``xdg-user-dir DESKTOP`` →
    ~/Bureau → ~/Desktop (logique historique de bureau_engine._bureau_dir)."""
    if IS_WINDOWS:
        for cand in (_win_known_folder(_FOLDERID_DESKTOP), _win_registry_desktop()):
            if cand and os.path.isdir(cand):
                return cand
        return os.path.join(HOME, "Desktop")
    r = run_cmd(["xdg-user-dir", "DESKTOP"], timeout=4)
    out = (r.stdout or "").strip()
    if r.returncode == 0 and out and os.path.isdir(out):
        return out
    for cand in (os.path.join(HOME, "Bureau"), os.path.join(HOME, "Desktop")):
        if os.path.isdir(cand):
            return cand
    return os.path.join(HOME, "Bureau")


def user_desktop_dir() -> str:
    """Alias de desktop_dir() (nom demandé par serveur.py)."""
    return desktop_dir()


def app_launcher_dirs() -> list[str]:
    """Répertoires de lanceurs à scanner en plus du Bureau (existants seulement).
    Linux : ~/.local/share/applications ; Windows : menus Démarrer utilisateur
    et machine (.lnk/.url)."""
    if IS_WINDOWS:
        cands = [os.path.join(os.environ.get("APPDATA", ""), r"Microsoft\Windows\Start Menu\Programs"),
                 os.path.join(os.environ.get("ProgramData", r"C:\ProgramData"),
                              r"Microsoft\Windows\Start Menu\Programs")]
    else:
        cands = [os.path.join(HOME, ".local", "share", "applications")]
    return [c for c in cands if c and os.path.isdir(c)]


def chrome_history_path() -> str:
    """Fichier History de Chrome (copie nécessaire : verrouillé quand Chrome tourne)."""
    if IS_WINDOWS:
        return os.path.join(os.environ.get("LOCALAPPDATA", HOME),
                            r"Google\Chrome\User Data\Default\History")
    return os.path.join(HOME, ".config", "google-chrome", "Default", "History")


def volume_by_label(label: str) -> str | None:
    """Point de montage d'un volume par étiquette : 'JARVIS-M1' → 'E:\\\\'
    (Windows, GetLogicalDrives + GetVolumeInformationW) ou
    '/media/<user>/JARVIS-M1' (Linux : /media/*/label, /run/media/*/label, /mnt/label)."""
    if not label:
        return None
    if IS_WINDOWS:
        try:
            import ctypes
            k32 = ctypes.windll.kernel32
            old_mode = k32.SetErrorMode(0x0001 | 0x0002)  # pas de boîte « insérez un disque »
            try:
                mask = k32.GetLogicalDrives()
                for i in range(26):
                    if not mask & (1 << i):
                        continue
                    root = f"{chr(65 + i)}:\\"
                    if k32.GetDriveTypeW(root) in (0, 1, 5):  # inconnu / pas de racine / CD-ROM
                        continue
                    buf = ctypes.create_unicode_buffer(261)
                    ok = k32.GetVolumeInformationW(root, buf, 261, None, None, None, None, 0)
                    if ok and buf.value.lower() == label.lower():
                        return root
            finally:
                k32.SetErrorMode(old_mode)
        except Exception:
            return None
        return None
    import glob
    for pat in (f"/media/*/{label}", f"/run/media/*/{label}", f"/mnt/{label}", f"/media/{label}"):
        for cand in glob.glob(pat):
            if os.path.isdir(cand):
                return cand
    return None


def safe_join(base_dir: str, url_path: str) -> str | None:
    """Joint un chemin d'URL sous ``base_dir`` en refusant tout échappement :
    chemins absolus, lettres de lecteur (``os.path.join(base, 'C:/x') == 'C:/x'``
    sous Windows), ``..``. None si hors base → 404 côté serveur."""
    if url_path is None:
        return None
    rel = str(url_path).replace("\\", "/")
    rel = rel.split("?", 1)[0].split("#", 1)[0]
    if rel.startswith("//"):  # UNC / protocole-relatif : refusé d'emblée
        return None
    rel = rel.lstrip("/")
    if not rel:
        return os.path.normpath(base_dir)
    if re.match(r"^[A-Za-z]:", rel) or os.path.isabs(rel):
        return None
    if any(seg == ".." for seg in rel.split("/")):
        return None
    base = os.path.normpath(os.path.abspath(base_dir))
    full = os.path.normpath(os.path.join(base, *[s for s in rel.split("/") if s and s != "."]))
    try:
        if os.path.commonpath([base, full]) != base:
            return None
    except ValueError:
        return None
    return full


def set_executable(path: str) -> bool:
    """chmod +x sous POSIX ; no-op (True) sous Windows. Ne lève jamais."""
    if IS_WINDOWS:
        return True
    try:
        st = os.stat(path)
        os.chmod(path, st.st_mode | 0o111)
        return True
    except OSError:
        return False


# ═══════════════════════════════════════════════════════════════════════════
#  RÉSOLUTION D'EXÉCUTABLES
# ═══════════════════════════════════════════════════════════════════════════

def _pathext() -> tuple[str, ...]:
    if not IS_WINDOWS:
        return ("",)
    raw = os.environ.get("PATHEXT", "")
    exts = tuple(e.lower() for e in raw.split(";") if e.strip()) or _PATHEXT_DEFAULT
    return ("",) + exts


def _is_wsl_bash(path: str | None) -> bool:
    """Vrai si ``path`` est le lanceur WSL (C:\\Windows\\System32\\bash.exe)."""
    if not path or not IS_WINDOWS:
        return False
    low = os.path.normcase(os.path.abspath(path))
    sysroot = os.path.normcase(os.environ.get("SystemRoot", r"C:\Windows"))
    return low.startswith(sysroot) and os.path.basename(low) in ("bash.exe", "sh.exe")


def bash_exe() -> str | None:
    """Vrai bash POSIX pour exécuter des .sh : Windows → Git bash
    (Program Files\\Git\\bin ou usr\\bin) sinon None — JAMAIS System32\\bash.exe
    (WSL). Linux → shutil.which('bash') ou /bin/bash."""
    if IS_WINDOWS:
        for cand in _WIN_CANDIDATES["bash"]:
            p = _expand(cand)
            if os.path.isfile(p) and not _is_wsl_bash(p):
                return p
        return None
    return shutil.which("bash") or ("/bin/bash" if os.path.exists("/bin/bash") else None)


def find_executable(name: str, *candidates: str) -> str | None:
    """Résout un CLI : chemin explicite (contient un séparateur) → tel quel s'il
    existe ; sinon shutil.which (PATHEXT honoré sous Windows) ; puis chaque
    candidat explicite (expandvars + expanduser). ``bash``/``sh`` sous Windows
    → Git bash uniquement (jamais le lanceur WSL)."""
    if not name:
        return None
    if os.sep in name or (IS_WINDOWS and "/" in name):
        p = _expand(name)
        return p if os.path.isfile(p) else None
    if IS_WINDOWS and name.lower() in ("bash", "sh", "bash.exe", "sh.exe"):
        key = "sh" if name.lower().startswith("sh") else "bash"
        for cand in _WIN_CANDIDATES[key] + tuple(candidates):
            p = _expand(cand)
            if os.path.isfile(p) and not _is_wsl_bash(p):
                return p
        return None
    found = shutil.which(name)
    if found:
        return found
    for cand in candidates:
        p = _expand(cand)
        if os.path.isfile(p):
            return p
    return None


@functools.lru_cache(maxsize=256)
def _which_cached(name: str, extra_dirs: tuple[str, ...]) -> str | None:
    if IS_WINDOWS and name.lower() in LINUX_ONLY_TOOLS:
        return None
    if IS_WINDOWS:
        key = name.lower()
        if key.endswith(".exe"):
            key = key[:-4]
        found = find_executable(name, *_WIN_CANDIDATES.get(key, ()))
        if found:
            return found
        for d in extra_dirs + _WIN_EXTRA_DIRS:
            d = _expand(d)
            if not os.path.isdir(d):
                continue
            for ext in _pathext():
                p = os.path.join(d, name + ext)
                if os.path.isfile(p) and not _is_wsl_bash(p):
                    return p
        return None
    found = shutil.which(name)
    if found:
        return found
    for d in extra_dirs:
        p = os.path.join(_expand(d), name)
        if os.path.isfile(p) and os.access(p, os.X_OK):
            return p
    return None


def which(name: str, extra_dirs: list[str] | tuple[str, ...] | None = None) -> str | None:
    """shutil.which + table Windows des emplacements connus (+ .exe/.cmd/.bat) ;
    les outils Linux-only (tmux, gnome-terminal, xdg-open, systemctl, loginctl…)
    rendent None sous Windows. Résultat mémoïsé (which_cache_clear() pour vider)."""
    if not name:
        return None
    return _which_cached(name, tuple(extra_dirs or ()))


def which_cache_clear() -> None:
    _which_cached.cache_clear()
    _feature_cached.cache_clear()


def python_exe() -> str:
    """Interpréteur courant (sys.executable) — jamais 'python3' (alias Store
    sous Windows). Sous pythonw.exe, préfère python.exe voisin pour les scripts
    dont on capture la sortie."""
    exe = sys.executable or "python3"
    if IS_WINDOWS and os.path.basename(exe).lower() == "pythonw.exe":
        cand = os.path.join(os.path.dirname(exe), "python.exe")
        if os.path.isfile(cand):
            return cand
    return exe


def python_executable() -> str:
    """Alias de python_exe() (nom demandé par les onglets)."""
    return python_exe()


def nvidia_smi_exe() -> str | None:
    """Chemin de nvidia-smi (PATH, puis System32, puis NVSMI) ; None si absent."""
    return which("nvidia-smi")


def nvidia_smi_path() -> str | None:
    """Alias de nvidia_smi_exe()."""
    return nvidia_smi_exe()


def tmux_path() -> str | None:
    """shutil.which('tmux') sous Linux ; TOUJOURS None sous Windows (pas de tmux
    Git-bash/WSL transparent : démarrage à froid de plusieurs secondes)."""
    if IS_WINDOWS:
        return None
    return shutil.which("tmux")


def tmux_available() -> bool:
    return tmux_path() is not None


def find_browser() -> str | None:
    """Binaire Chrome/BrowserOS : Linux → ~/.local/bin/browseros, /opt/browseros…,
    google-chrome ; Windows → chrome.exe puis msedge.exe. None si rien."""
    if IS_WINDOWS:
        return which("chrome") or which("msedge")
    for cand in (os.path.join(HOME, ".local", "bin", "browseros"),
                 "/opt/browseros/opt/browseros/browseros",
                 "/usr/bin/google-chrome", "/opt/google/chrome/chrome"):
        if os.path.isfile(cand) and os.access(cand, os.X_OK):
            return cand
    return (shutil.which("google-chrome") or shutil.which("google-chrome-stable")
            or shutil.which("chromium") or shutil.which("chromium-browser"))


def find_app(name: str) -> str | None:
    """Applications connues par plateforme → chemin exécutable ou None.
    Clés : claude, claude-desktop, chrome, browseros, ollama, docker, wt,
    nvidia-smi, git, sqlite3, tmux, agy, lms, lmstudio, ffmpeg, tailscale, code…"""
    key = (name or "").lower().strip()
    if not key:
        return None
    if key in ("chrome", "browseros"):
        if key == "browseros" and not IS_WINDOWS:
            for cand in (os.path.join(HOME, ".local", "bin", "browseros"),
                         "/opt/browseros/opt/browseros/browseros"):
                if os.path.isfile(cand):
                    return cand
        return find_browser()
    if key == "claude-desktop":
        if IS_WINDOWS:
            return which("claude-desktop")
        return "/usr/bin/claude-desktop" if os.path.isfile("/usr/bin/claude-desktop") else shutil.which("claude-desktop")
    if key == "claude":
        found = which("claude")
        if found:
            return found
        for cand in (os.path.join(HOME, ".local", "bin", "claude.exe" if IS_WINDOWS else "claude"),):
            if os.path.isfile(cand):
                return cand
        return None
    if key == "tmux":
        return tmux_path()
    return which(key)


def exec_head(exec_cmd: str) -> str:
    """Premier mot d'une ligne de commande en respectant les guillemets :
    ``"C:\\Program Files\\X\\x.exe" --flag`` → ``C:\\Program Files\\X\\x.exe``."""
    s = (exec_cmd or "").strip()
    if not s:
        return ""
    try:
        parts = shlex.split(s, posix=not IS_WINDOWS)
    except ValueError:
        parts = s.split()
    if not parts:
        return ""
    head = parts[0]
    if IS_WINDOWS:
        head = head.strip('"').strip("'")
    return head


# ═══════════════════════════════════════════════════════════════════════════
#  SOUS-PROCESSUS
# ═══════════════════════════════════════════════════════════════════════════

def no_window_kwargs() -> dict:
    """{'creationflags': CREATE_NO_WINDOW} sous Windows, {} ailleurs — à passer
    en **kwargs à chaque subprocess.run/Popen/check_output d'outil console."""
    return {"creationflags": NO_WINDOW} if IS_WINDOWS else {}


def popen_detached_kwargs(new_console: bool = False) -> dict:
    """kwargs pour détacher un enfant : Linux → start_new_session=True ;
    Windows → creationflags=CREATE_NEW_PROCESS_GROUP | (CREATE_NEW_CONSOLE si
    new_console sinon CREATE_NO_WINDOW). (preexec_fn lève ValueError sous Windows.)"""
    if IS_WINDOWS:
        return {"creationflags": _NEW_GROUP | (_NEW_CONSOLE if new_console else NO_WINDOW)}
    return {"start_new_session": True}


def _win_env(env: dict | None) -> dict | None:
    """Sous Windows un env partiel casse CreateProcess (SystemRoot absent)."""
    if env is None or not IS_WINDOWS:
        return env
    env = dict(env)
    for k in ("SystemRoot", "SYSTEMROOT", "windir"):
        if k in os.environ and k not in env:
            env[k] = os.environ[k]
    if "PATH" not in env and "Path" not in env:
        env["PATH"] = os.environ.get("PATH", "")
    return env


@functools.lru_cache(maxsize=1)
def _oem_codepage() -> str:
    """Page de code console Windows ('cp850' en France) pour décoder les outils
    natifs qui n'écrivent pas en UTF-8 (cmd.exe, schtasks, tasklist…)."""
    if not IS_WINDOWS:
        return "utf-8"
    try:
        import ctypes
        k32 = ctypes.windll.kernel32
        cp = k32.GetConsoleOutputCP() or k32.GetOEMCP()
        if cp:
            return f"cp{cp}"
    except Exception:
        pass
    return "cp850"


def decode_output(data: bytes | str | None) -> str:
    """bytes de sous-processus → str : UTF-8 strict, sinon page de code OEM
    (Windows) avec errors='replace'. Jamais d'UnicodeDecodeError."""
    if not data:
        return ""
    if isinstance(data, str):
        return data
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        pass
    if IS_WINDOWS:
        try:
            return data.decode(_oem_codepage(), "replace")
        except LookupError:
            pass
    return data.decode("utf-8", "replace")


def _child_env(env: dict | None) -> dict | None:
    """Env du sous-processus : complété (SystemRoot/PATH sous Windows) et, sous
    Windows, forcé en UTF-8 pour les enfants Python (PYTHONUTF8/PYTHONIOENCODING)
    afin que run_cmd les décode sans mojibake."""
    if not IS_WINDOWS:
        return env
    env = dict(env if env is not None else os.environ)
    env = _win_env(env)
    env.setdefault("PYTHONUTF8", "1")
    env.setdefault("PYTHONIOENCODING", "utf-8")
    return env


def run_cmd(cmd: list[str] | str, timeout: float = 10.0, cwd: str | None = None,
            input_text: str | None = None, env: dict | None = None,
            shell: bool = False, **kw) -> subprocess.CompletedProcess:
    """Exécution bornée qui NE LÈVE JAMAIS : sortie capturée, décodée en UTF-8
    (repli page de code OEM) errors='replace', CREATE_NO_WINDOW sous Windows,
    stdin fermé (aucun outil ne peut bloquer sur une question). Au dépassement
    de délai TOUT l'arbre est tué (taskkill /T sous Windows : un `cmd /c python`
    orphelin ne garde pas le tube ouvert).
    Échecs → CompletedProcess(returncode≠0, stderr explicite) :
      127 commande introuvable · 124 dépassement de délai · 1 autre OSError."""
    argv = cmd
    if isinstance(cmd, str) and not shell:
        try:
            argv = shlex.split(cmd, posix=not IS_WINDOWS)
        except ValueError:
            argv = cmd.split()
    head = argv[0] if isinstance(argv, (list, tuple)) and argv else str(cmd)
    kwargs = dict(stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                  stdin=subprocess.PIPE if input_text is not None else subprocess.DEVNULL,
                  cwd=cwd or None, env=_child_env(env), shell=shell)
    if IS_WINDOWS:
        kwargs["creationflags"] = kw.pop("creationflags", 0) | NO_WINDOW
    for k in ("capture_output", "text", "encoding", "errors", "universal_newlines", "input"):
        kw.pop(k, None)
    kwargs.update(kw)
    try:
        proc = subprocess.Popen(argv, **kwargs)
    except FileNotFoundError:
        return subprocess.CompletedProcess(argv, 127, "", f"commande introuvable : {head}")
    except (OSError, ValueError, subprocess.SubprocessError) as e:
        return subprocess.CompletedProcess(argv, 1, "", f"{type(e).__name__}: {e}")
    data = input_text.encode("utf-8", "replace") if input_text is not None else None
    try:
        out, err = proc.communicate(data, timeout=timeout)
    except subprocess.TimeoutExpired:
        kill_process_tree(proc, graceful_delay=0.0)
        try:
            out, err = proc.communicate(timeout=5)
        except Exception:
            out, err = b"", b""
        return subprocess.CompletedProcess(argv, 124, decode_output(out), f"dépassement de {timeout:g}s")
    except (OSError, ValueError) as e:
        kill_process_tree(proc, graceful_delay=0.0)
        return subprocess.CompletedProcess(argv, 1, "", f"{type(e).__name__}: {e}")
    return subprocess.CompletedProcess(argv, proc.returncode, decode_output(out), decode_output(err))


def run_cmd_ok(cmd: list[str], timeout: float = 6, env: dict | None = None,
               cwd: str | None = None) -> tuple[bool, str]:
    """Contrat de inventaire._run : (ok, sortie) — stdout sinon stderr, strip.
    FileNotFoundError → (False, 'commande introuvable : X'),
    TimeoutExpired → (False, 'dépassement de Ns')."""
    r = run_cmd(cmd, timeout=timeout, env=env, cwd=cwd)
    return r.returncode == 0, ((r.stdout or r.stderr or "")).strip()


def win_shell_kind() -> str:
    """Shell utilisé pour les COMMANDES TEXTE sous Windows : 'cmd' (défaut),
    'powershell', 'pwsh' ou 'gitbash' — variable JARVIS_WIN_SHELL."""
    k = os.environ.get("JARVIS_WIN_SHELL", "cmd").strip().lower()
    if k in ("ps", "ps1", "powershell.exe"):
        k = "powershell"
    if k in ("git-bash", "git_bash", "bash"):
        k = "gitbash"
    if k == "gitbash" and not bash_exe():
        k = "cmd"
    if k in ("pwsh", "powershell") and not which(k):
        k = "powershell" if which("powershell") else "cmd"
    return k if k in ("cmd", "powershell", "pwsh", "gitbash") else "cmd"


def default_shell(login: bool = True) -> list[str]:
    """argv du shell interactif à offrir : Linux → ['/bin/bash', '-il'|'-i'] ;
    Windows → pwsh.exe / powershell.exe -NoLogo -NoExit (jamais 'bash' nu)."""
    if IS_WINDOWS:
        exe = which("pwsh") or which("powershell") or "powershell.exe"
        return [exe, "-NoLogo", "-NoExit"]
    bash = bash_exe() or "/bin/bash"
    return [bash, "-il" if login else "-i"]


def shell_wrap(command: str, keep_open: bool = False, interactive: bool = False) -> list[str]:
    """argv exécutant une chaîne de commande via le shell de la plateforme.
    Linux → ['/bin/bash', '-lc'|'-ic', cmd] (+ '; exec /bin/bash -i' si keep_open).
    Windows (selon win_shell_kind) → ['cmd.exe','/d','/c'|'/k', cmd] ;
    powershell/pwsh → [exe,'-NoProfile','-ExecutionPolicy','Bypass',('-NoExit'),'-Command',cmd] ;
    gitbash → [bash.exe,'-lc',cmd]. À passer tel quel à wt.exe / gnome-terminal."""
    if IS_WINDOWS:
        kind = win_shell_kind()
        if kind in ("powershell", "pwsh"):
            exe = which(kind) or "powershell.exe"
            argv = [exe, "-NoProfile", "-ExecutionPolicy", "Bypass"]
            if keep_open:
                argv.append("-NoExit")
            return argv + ["-Command", command]
        if kind == "gitbash":
            tail = f"{command}; exec bash -i" if keep_open else command
            return [bash_exe(), "-lc", tail]
        return ["cmd.exe", "/d", "/k" if keep_open else "/c", command]
    bash = bash_exe() or "/bin/bash"
    tail = f"{command}; exec {bash} -i" if keep_open else command
    return [bash, "-ic" if interactive else "-lc", tail]


class ShellResult(subprocess.CompletedProcess):
    """CompletedProcess + accès dict ('stdout','stderr','code','success') et
    .to_dict() pour les réponses JSON de serveur.py."""

    @property
    def code(self) -> int:
        return self.returncode

    @property
    def success(self) -> bool:
        return self.returncode == 0

    def to_dict(self) -> dict:
        return {"stdout": self.stdout or "", "stderr": self.stderr or "",
                "code": self.returncode, "success": self.success,
                "returncode": self.returncode}

    def __getitem__(self, key):
        return self.to_dict()[key]

    def get(self, key, default=None):
        return self.to_dict().get(key, default)


def run_shell(command: str, timeout: float = 25.0, cwd: str | None = None,
              env: dict | None = None, interactive: bool = False) -> ShellResult:
    """Exécute une LIGNE DE COMMANDE utilisateur : Linux → bash -lc (inchangé) ;
    Windows → cmd.exe /c (ou PowerShell / Git bash selon JARVIS_WIN_SHELL), sans
    fenêtre, UTF-8 errors='replace'. Jamais d'exception : code 124/127/1 +
    stderr explicite. Résultat utilisable comme CompletedProcess ou dict."""
    if IS_WINDOWS and win_shell_kind() == "cmd":
        # Python construit lui-même `cmd.exe /c "…"` correctement (guillemets
        # internes préservés) : plus sûr qu'une liste ['cmd','/c', cmd].
        r = run_cmd(command, timeout=timeout, cwd=cwd, env=env, shell=True)
    else:
        r = run_cmd(shell_wrap(command, interactive=interactive), timeout=timeout, cwd=cwd, env=env)
    return ShellResult(r.args, r.returncode, r.stdout or "", r.stderr or "")


def run_shell_script(script_path: str, args: list[str] | None = None,
                     timeout: float = 10.0, cwd: str | None = None) -> subprocess.CompletedProcess | None:
    """Exécute un script bash : Linux → ['bash', script, *args] ; Windows →
    uniquement Git bash (jamais 'bash' nu = WSL). None si aucun bash utilisable
    (l'appelant renvoie unavailable(...)) ou si le script est absent."""
    bash = bash_exe()
    if not bash or not script_path or not os.path.isfile(script_path):
        return None
    return run_cmd([bash, script_path, *(args or [])], timeout=timeout, cwd=cwd)


def run_python_script(script_rel: str, args: list[str] | tuple[str, ...] = (), timeout: float = 30,
                      cwd: str | None = None) -> subprocess.CompletedProcess | None:
    """[python_exe(), jarvis_path(script_rel), *args] avec capture ; None si le
    script est absent, en délai dépassé ou introuvable (jamais d'exception).
    ``script_rel`` peut aussi être un chemin absolu."""
    script = script_rel if os.path.isabs(script_rel) else jarvis_path(script_rel)
    if not script or not os.path.isfile(script):
        return None
    r = run_cmd([python_exe(), script, *list(args)], timeout=timeout, cwd=cwd)
    if r.returncode in (124, 127):
        return None
    return r


def popen_detached(cmd: list[str] | str, cwd: str | None = None, shell: bool = False,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                   env: dict | None = None, new_console: bool = False, **kw) -> subprocess.Popen:
    """Popen détaché portable (LÈVE FileNotFoundError normalement, l'appelant
    rattrape — voir safe_popen pour la version silencieuse).
    Linux → start_new_session=True, stdout/stderr DEVNULL ; Windows →
    DETACHED_PROCESS|CREATE_NEW_PROCESS_GROUP (ou CREATE_NEW_CONSOLE si
    new_console), close_fds=True."""
    kwargs = dict(cwd=cwd or None, shell=shell, stdout=stdout, stderr=stderr,
                  stdin=kw.pop("stdin", subprocess.DEVNULL), env=_win_env(env))
    if IS_WINDOWS:
        flags = kw.pop("creationflags", 0) | _NEW_GROUP
        flags |= _NEW_CONSOLE if new_console else _DETACHED
        kwargs["creationflags"] = flags
        kwargs["close_fds"] = True
    else:
        kwargs["start_new_session"] = True
    kwargs.update(kw)
    return subprocess.Popen(cmd, **kwargs)


def safe_popen(cmd: list[str] | str, *, shell: bool = False, cwd: str | None = None,
               detach: bool = True, **kw) -> subprocess.Popen | None:
    """Popen qui NE LÈVE JAMAIS (FileNotFoundError/OSError/PermissionError →
    None + trace sur stderr). detach=True ⇒ popen_detached. Un suffixe ' &'
    (forme shell Linux) est retiré sous Windows."""
    if IS_WINDOWS and isinstance(cmd, str):
        cmd = cmd.rstrip()
        if cmd.endswith("&"):
            cmd = cmd[:-1].rstrip()
    try:
        if detach:
            return popen_detached(cmd, cwd=cwd, shell=shell, **kw)
        kwargs = dict(cwd=cwd or None, shell=shell)
        if IS_WINDOWS:
            kwargs["creationflags"] = kw.pop("creationflags", 0) | NO_WINDOW
        kwargs.update(kw)
        return subprocess.Popen(cmd, **kwargs)
    except (OSError, ValueError, subprocess.SubprocessError) as e:
        _log_err(f"safe_popen({cmd!r}) : {type(e).__name__}: {e}")
        return None


def launch_detached(cmd: str | list[str], cwd: str | None = None) -> bool:
    """Lancement « fire-and-forget » d'une application : Linux →
    bash -lc cmd détaché ; Windows → os.startfile si c'est un chemin/URL
    existant, sinon Popen(shell=True) détaché sans fenêtre. False sans lever."""
    try:
        if IS_WINDOWS:
            if isinstance(cmd, str):
                s = cmd.strip()
                if _looks_like_url(s) or os.path.exists(s.strip('"')):
                    os.startfile(s.strip('"'))  # noqa: S606 — association système
                    return True
                return _track(popen_detached(s, cwd=cwd, shell=True)) is not None
            return _track(popen_detached(list(cmd), cwd=cwd)) is not None
        if isinstance(cmd, str):
            return _track(popen_detached([bash_exe() or "/bin/bash", "-lc", cmd], cwd=cwd)) is not None
        return _track(popen_detached(list(cmd), cwd=cwd)) is not None
    except Exception as e:
        _log_err(f"launch_detached({cmd!r}) : {type(e).__name__}: {e}")
        return False


_DETACHED_CHILDREN: list[subprocess.Popen] = []


def _track(proc: subprocess.Popen | None) -> subprocess.Popen | None:
    """Garde une référence aux enfants « fire-and-forget » (évite le
    ResourceWarning « subprocess is still running ») et purge les terminés."""
    _DETACHED_CHILDREN[:] = [p for p in _DETACHED_CHILDREN if p.poll() is None]
    if proc is not None:
        _DETACHED_CHILDREN.append(proc)
    return proc


def _looks_like_url(s: str) -> bool:
    return bool(re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", s or ""))


def open_path(target: str) -> bool:
    """Ouvre un fichier/dossier/URL avec l'application par défaut :
    os.startfile sous Windows, xdg-open (détaché) sous Linux, repli
    webbrowser pour les URL. Ne lève jamais."""
    return open_path_msg(target)[0]


def open_path_msg(target: str) -> tuple[bool, str]:
    """Comme open_path mais rend (ok, message français)."""
    if not target:
        return False, "chemin vide"
    try:
        if IS_WINDOWS:
            os.startfile(target)  # noqa: S606
            return True, f"ouvert : {target}"
        if shutil.which("xdg-open"):
            popen_detached(["xdg-open", target])
            return True, f"ouvert : {target}"
        if _looks_like_url(target) and webbrowser.open(target):
            return True, f"ouvert (navigateur) : {target}"
        return False, "xdg-open introuvable"
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


def open_url(url: str) -> bool:
    """Navigateur par défaut : os.startfile (Windows) / xdg-open, repli webbrowser."""
    if not url:
        return False
    if open_path(url):
        return True
    try:
        return bool(webbrowser.open(url))
    except Exception:
        return False


def open_chrome_app(url_or_file: str, width: int = 450, height: int = 600) -> subprocess.Popen | None:
    """find_browser() --app=<url> --window-size=W,H (fichier local → file:///).
    None sans lever si aucun navigateur."""
    browser = find_browser()
    if not browser or not url_or_file:
        return None
    target = url_or_file
    if not _looks_like_url(target):
        try:
            import pathlib
            target = pathlib.Path(target).resolve().as_uri()
        except Exception:
            return None
    return safe_popen([browser, f"--app={target}", f"--window-size={width},{height}"])


# ── terminaux graphiques ────────────────────────────────────────────────────

def _linux_terminal() -> str | None:
    for t in ("gnome-terminal", "x-terminal-emulator", "xterm", "xfce4-terminal",
              "konsole", "tilix", "alacritty", "kitty", "foot"):
        found = shutil.which(t)
        if found:
            return found
    if IS_WSL:
        for t in ("wt.exe", "cmd.exe"):
            found = shutil.which(t)
            if found:
                return found
    return None


def _command_to_string(command) -> str:
    if isinstance(command, str):
        return command
    return subprocess.list2cmdline(list(command)) if IS_WINDOWS else shlex.join(list(command))


def terminal_argv(command: str | list[str] | None = None, title: str = "JARVIS",
                  cwd: str | None = None, keep_open: bool = True,
                  login_shell: bool = False) -> tuple[list[str] | None, dict]:
    """(argv, kwargs Popen) de la fenêtre de terminal à ouvrir, ou (None, {})
    si aucun émulateur. Exposé pour les tests ; open_terminal l'exécute."""
    title = title or "JARVIS"
    if IS_WINDOWS:
        if command is None:
            shell_argv = default_shell()
        else:
            shell_argv = shell_wrap(_command_to_string(command), keep_open=keep_open)
        wt = which("wt")
        if wt:
            argv = [wt, "-w", "0", "new-tab", "--title", title, "-d", cwd or HOME] + shell_argv
            return argv, {"cwd": cwd or None, **popen_detached_kwargs()}
        # Repli : console classique (title posé via la commande interne)
        if command is None:
            argv = shell_argv
        elif shell_argv[0].lower().startswith("cmd"):
            argv = ["cmd.exe", "/d", shell_argv[2], f"title {title} & {shell_argv[3]}"]
        else:
            argv = shell_argv
        return argv, {"cwd": cwd or None, **popen_detached_kwargs(new_console=True)}
    term = _linux_terminal()
    if not term:
        return None, {}
    base_t = os.path.basename(term).lower()
    if base_t in ("wt.exe", "wt"):
        cmd_str = _command_to_string(command) if command else None
        if not cmd_str:
            wsl_argv = ["wsl.exe", "-e", "bash", "-il"]
        elif keep_open:
            wsl_argv = ["wsl.exe", "-e", "bash", "-ic" if login_shell else "-c", f"{cmd_str}; exec bash -i"]
        elif isinstance(command, (list, tuple)):
            wsl_argv = ["wsl.exe", "-e"] + list(command)
        else:
            wsl_argv = ["wsl.exe", "-e", "bash", "-ic" if login_shell else "-c", cmd_str]
        argv = [term, "-w", "0", "new-tab", "--title", title, "-d", cwd or HOME] + wsl_argv
        return argv, {"cwd": cwd or None, **popen_detached_kwargs()}
    elif base_t in ("cmd.exe", "cmd"):
        cmd_str = _command_to_string(command) if command else None
        if not cmd_str:
            wsl_argv = "wsl.exe -e bash -il"
        else:
            wsl_argv = f"wsl.exe -e bash -ic \"{cmd_str}; exec bash -i\"" if keep_open else f"wsl.exe -e bash -c \"{cmd_str}\""
        argv = [term, "/k", f"title {title} & {wsl_argv}"]
        return argv, {"cwd": cwd or None, **popen_detached_kwargs()}
    if command is None:
        shell_argv = default_shell()
    elif isinstance(command, str):
        shell_argv = shell_wrap(command, keep_open=keep_open, interactive=login_shell)
    elif keep_open:
        shell_argv = shell_wrap(shlex.join(list(command)), keep_open=True, interactive=login_shell)
    else:
        shell_argv = list(command)
    if base_t == "xterm":
        argv = [term, "-T", title, "-e"] + shell_argv
    else:
        argv = [term, "--title", title, "--"] + shell_argv
    return argv, {"cwd": cwd or None, **popen_detached_kwargs()}


def open_terminal(command: str | list[str] | None = None, title: str = "JARVIS",
                  cwd: str | None = None, keep_open: bool = True,
                  login_shell: bool = False, hold: bool | None = None) -> subprocess.Popen | None:
    """Ouvre une NOUVELLE fenêtre de terminal exécutant ``command`` (str ou argv ;
    None → shell interactif) et la laisse ouverte ensuite (keep_open/hold).
    Linux : gnome-terminal / x-terminal-emulator / xterm --title T -- bash -lc
    '<cmd>; exec bash -i' (login_shell=True ⇒ bash -ic pour les alias ttx/agy…).
    WSL : repli transparent vers Windows Terminal (wt.exe) ou cmd.exe si aucun terminal X11.
    Windows : wt.exe -w 0 new-tab --title T -d cwd <shell_wrap(cmd)> ; repli
    cmd.exe /k dans une nouvelle console. NE LÈVE JAMAIS : Popen (truthy) ou None."""
    if hold is not None:
        keep_open = hold
    try:
        argv, kwargs = terminal_argv(command, title=title, cwd=cwd, keep_open=keep_open,
                                     login_shell=login_shell)
        if not argv:
            _log_err("open_terminal : aucun émulateur de terminal disponible")
            return None
        return subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL, **kwargs)
    except Exception as e:
        _log_err(f"open_terminal({command!r}) : {type(e).__name__}: {e}")
        return None


def open_in_terminal(cmd: str | list[str], title: str = "JARVIS",
                     cwd: str | None = None) -> tuple[bool, str]:
    """Variante (ok, message) de open_terminal pour apps_registry / tab_apps."""
    p = open_terminal(cmd, title=title, cwd=cwd, keep_open=True)
    if p is None:
        return False, "aucun terminal disponible (wt.exe / gnome-terminal introuvable)"
    return True, f"terminal ouvert (pid {p.pid}) : {title}"


# ── signaux / arbres de processus ──────────────────────────────────────────

def signal_by_name(name: str) -> int | None:
    """'INT'/'TERM'/'QUIT'/'KILL'/'HUP' → numéro de signal disponible ici.
    Windows : INT → CTRL_BREAK_EVENT (enfant créé avec CREATE_NEW_PROCESS_GROUP),
    TERM/KILL/HUP → SIGTERM, QUIT → None."""
    key = (name or "").upper().replace("SIG", "", 1) if (name or "").upper().startswith("SIG") else (name or "").upper()
    if IS_WINDOWS:
        return {"INT": getattr(signal, "CTRL_BREAK_EVENT", None),
                "TERM": signal.SIGTERM, "KILL": signal.SIGTERM,
                "HUP": signal.SIGTERM}.get(key)
    return getattr(signal, f"SIG{key}", None)


def send_signal_group(proc: subprocess.Popen, sig: int) -> bool:
    """Linux : os.killpg(getpgid(pid), sig) (repli proc.send_signal si pas de
    groupe) ; Windows : proc.send_signal(sig). False au lieu de lever."""
    if proc is None or sig is None:
        return False
    try:
        if IS_WINDOWS or not hasattr(os, "killpg"):
            proc.send_signal(sig)
            return True
        try:
            pgid = os.getpgid(proc.pid)
        except (ProcessLookupError, PermissionError):
            proc.send_signal(sig)
            return True
        # killpg SEULEMENT si l'enfant mène son propre groupe (start_new_session) :
        # sinon on signalerait notre propre groupe, cockpit compris.
        if pgid == proc.pid:
            os.killpg(pgid, sig)
        else:
            for child in _descendants(proc.pid):
                try:
                    child.send_signal(sig)
                except Exception:
                    pass
            proc.send_signal(sig)
        return True
    except (OSError, ValueError, AttributeError):
        return False


def _descendants(pid: int) -> list:
    """Descendants (psutil) d'un pid, [] sans psutil ou si introuvable."""
    ps = _psutil()
    if ps is None:
        return []
    try:
        return ps.Process(pid).children(recursive=True)
    except Exception:
        return []


def kill_process_tree(proc: subprocess.Popen, graceful_delay: float = 0.15) -> None:
    """Linux : SIGHUP au groupe, pause, SIGKILL si encore vivant (logique de
    Session.fermer). Windows : terminate() puis taskkill /T /F /PID (enfants
    compris). Ne lève jamais."""
    if proc is None:
        return
    try:
        if proc.poll() is not None:
            return
    except Exception:
        return
    if IS_WINDOWS:
        try:
            proc.terminate()
        except (OSError, AttributeError):
            pass
        try:  # subprocess.run direct : pas de récursion via run_cmd
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)], timeout=8,
                           stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL, creationflags=NO_WINDOW)
        except (OSError, subprocess.SubprocessError):
            pass
        _reap(proc)
        return
    try:
        hup = getattr(signal, "SIGHUP", signal.SIGTERM)
        if not send_signal_group(proc, hup):
            proc.terminate()
        time.sleep(max(0.0, graceful_delay))
        if proc.poll() is None:
            if not send_signal_group(proc, getattr(signal, "SIGKILL", signal.SIGTERM)):
                proc.kill()
    except (OSError, ProcessLookupError, AttributeError):
        pass
    _reap(proc)


def _reap(proc: subprocess.Popen, timeout: float = 2.0) -> None:
    """wait() court après un kill : évite zombies et ResourceWarning."""
    try:
        proc.wait(timeout=timeout)
    except Exception:
        pass


def process_running(pattern: str) -> bool:
    """Équivalent de ``pgrep -f <regex>`` via psutil (nom + cmdline), sans le
    processus courant. Repli pgrep sous Linux sans psutil ; False sinon."""
    return len(_matching_processes(pattern)) > 0


def _matching_processes(pattern: str) -> list:
    ps = _psutil()
    if not pattern:
        return []
    try:
        rx = re.compile(pattern)
    except re.error:
        rx = re.compile(re.escape(pattern))
    if ps is None:
        if IS_LINUX and shutil.which("pgrep"):
            r = run_cmd(["pgrep", "-f", pattern], timeout=4)
            pids = [int(x) for x in (r.stdout or "").split() if x.isdigit() and int(x) != os.getpid()]
            return [SimpleNamespace(pid=p) for p in pids]
        return []
    found = []
    me = os.getpid()
    for p in ps.process_iter(["pid", "name", "cmdline"]):
        try:
            if p.info["pid"] == me:
                continue
            hay = " ".join([p.info.get("name") or ""] + list(p.info.get("cmdline") or []))
            if rx.search(hay):
                found.append(p)
        except (ps.NoSuchProcess, ps.AccessDenied, ps.ZombieProcess):
            continue
    return found


def kill_processes_matching(pattern: str, timeout: float = 3.0) -> int:
    """Équivalent de ``pkill -f <regex>`` : terminate() puis kill() après
    timeout. Rend le nombre de processus tués. Repli pkill sous Linux."""
    procs = _matching_processes(pattern)
    ps = _psutil()
    if not procs:
        return 0
    if ps is None:
        if IS_LINUX and shutil.which("pkill"):
            run_cmd(["pkill", "-f", pattern], timeout=4)
            return len(procs)
        return 0
    n = 0
    for p in procs:
        try:
            p.terminate()
            n += 1
        except (ps.NoSuchProcess, ps.AccessDenied):
            pass
    try:
        _, alive = ps.wait_procs(procs, timeout=timeout)
        for p in alive:
            try:
                p.kill()
            except (ps.NoSuchProcess, ps.AccessDenied):
                pass
    except Exception:
        pass
    return n


# ═══════════════════════════════════════════════════════════════════════════
#  SESSIONS LOCALES (repli quand tmux est absent)
# ═══════════════════════════════════════════════════════════════════════════
#
# API pour l'onglet Terminal (G1) quand tmux_available() est False :
#   local_session_create(name, command=None, cwd=None, title=None) -> dict
#       ouvre une fenêtre de console (Windows : nouvelle console / onglet wt ;
#       Linux : gnome-terminal) qui exécute ``command`` (str, argv ou None =
#       shell) et l'enregistre. Rend le dict de la session (voir schéma).
#   local_sessions_list(include_dead=False) -> list[dict]
#       même schéma que get_active_tmux_sessions() : {name, windows, attached}
#       + {id, pid, alive, command, cwd, started, source='local'}.
#   local_session_get(name_or_id) -> dict | None
#   local_session_kill(name_or_id) -> bool   (kill_process_tree + retrait)
#   local_sessions_prune() -> int             (retire les sessions mortes)
# Les sessions ne survivent pas au redémarrage du cockpit (contrairement à tmux).

_LOCAL_SESSIONS: dict[str, dict] = {}
_LOCAL_LOCK = threading.Lock()


def _session_view(s: dict) -> dict:
    proc = s["proc"]
    alive = proc is not None and proc.poll() is None
    return {"id": s["id"], "name": s["name"], "windows": 1, "attached": alive,
            "alive": alive, "pid": proc.pid if proc else None, "command": s["command"],
            "cwd": s["cwd"], "started": s["started"], "source": "local",
            "returncode": None if alive else (proc.returncode if proc else None)}


def local_session_create(name: str | None = None, command: str | list[str] | None = None,
                         cwd: str | None = None, title: str | None = None) -> dict:
    """Crée une « session » locale = fenêtre de terminal + Popen enregistré.
    Jamais d'exception : en cas d'échec le dict porte alive=False et 'error'."""
    with _LOCAL_LOCK:
        sid = uuid.uuid4().hex[:8]
        name = (name or f"jc-{sid}").strip()
        base, k = name, 1
        while name in _LOCAL_SESSIONS:
            k += 1
            name = f"{base}-{k}"
        proc = open_terminal(command, title=title or name, cwd=cwd, keep_open=True)
        entry = {"id": sid, "name": name, "proc": proc, "command": _command_to_string(command) if command else "",
                 "cwd": cwd or HOME, "started": time.time()}
        _LOCAL_SESSIONS[name] = entry
        view = _session_view(entry)
        if proc is None:
            view["error"] = "aucun terminal disponible"
        return view


def local_sessions_list(include_dead: bool = False) -> list[dict]:
    with _LOCAL_LOCK:
        views = [_session_view(s) for s in _LOCAL_SESSIONS.values()]
    return views if include_dead else [v for v in views if v["alive"]]


def local_session_get(name_or_id: str) -> dict | None:
    with _LOCAL_LOCK:
        for s in _LOCAL_SESSIONS.values():
            if s["name"] == name_or_id or s["id"] == name_or_id:
                return _session_view(s)
    return None


def local_session_kill(name_or_id: str) -> bool:
    with _LOCAL_LOCK:
        key = next((n for n, s in _LOCAL_SESSIONS.items()
                    if n == name_or_id or s["id"] == name_or_id), None)
        if key is None:
            return False
        entry = _LOCAL_SESSIONS.pop(key)
    if entry["proc"] is not None:
        kill_process_tree(entry["proc"])
    return True


def local_sessions_prune() -> int:
    with _LOCAL_LOCK:
        dead = [n for n, s in _LOCAL_SESSIONS.items() if s["proc"] is None or s["proc"].poll() is not None]
        for n in dead:
            _LOCAL_SESSIONS.pop(n, None)
    return len(dead)


# ═══════════════════════════════════════════════════════════════════════════
#  MESSAGES / STUBS « INDISPONIBLE »
# ═══════════════════════════════════════════════════════════════════════════

def _platform_label() -> str:
    return "Windows" if IS_WINDOWS else ("macOS" if IS_MAC else "cette plateforme")


def _accord(feature: str) -> str:
    """'indisponible' ou 'indisponibles' selon le premier mot (Sessions → pluriel)."""
    first = (feature or "").strip().split(" ")[0].lower()
    return "indisponibles" if first.endswith(("s", "x")) and len(first) > 2 else "indisponible"


def unavailable_note(feature: str) -> str:
    """'⚠ Sessions tmux indisponibles sous Windows' — libellé canonique pour
    QLabel, lignes de table, tooltips et champs 'sortie' des réponses JSON."""
    return f"⚠ {feature} {_accord(feature)} sous {_platform_label()}"


def unavailable_message(feature: str, detail: str = "") -> str:
    """'⛔ {feature} : indisponible sous Windows — detail'."""
    msg = f"⛔ {feature} : indisponible sous {_platform_label()}"
    return f"{msg} — {detail}" if detail else msg


def unavailable(feature: str, **extra) -> dict:
    """Charge utile JSON standard des routes/actions Linux-only :
    {'success': False, 'unavailable': True, 'unsupported': True,
     'error': '<feature> indisponible sous Windows', 'note': idem, 'output': '',
     'plateforme': 'windows', **extra}."""
    msg = f"{feature} {_accord(feature)} sous {_platform_label()}"
    d = {"success": False, "unavailable": True, "unsupported": True,
         "error": msg, "note": msg, "output": "", "plateforme": PLATFORM_NAME}
    d.update(extra)
    return d


def indisponible(fonction: str, **extra) -> dict:
    """Stub « réussite vide » des façades bureau/inventaire :
    {'success': True, 'indisponible': True, 'plateforme': 'windows',
     'note': '<fonction> indisponible sous Windows'}."""
    d = {"success": True, "indisponible": True, "plateforme": PLATFORM_NAME,
         "note": f"{fonction} {_accord(fonction)} sous {_platform_label()}"}
    d.update(extra)
    return d


@functools.lru_cache(maxsize=64)
def _feature_cached(name: str) -> bool:
    n = name.lower()
    if IS_WINDOWS:
        if n in ("tmux", "gnome-terminal", "systemd", "journalctl", "arecord", "lumen",
                 "flo", "x11", "wayland", "appimage", "bash_scripts", "loginctl", "xdg-open"):
            return False
        if n == "docker":
            return which("docker") is not None
        if n == "cuda":
            return nvidia_smi_exe() is not None
        if n == "whisper_local":
            return importlib.util.find_spec("faster_whisper") is not None
        if n == "gitbash":
            return bash_exe() is not None
        if n in ("wt", "powershell", "pwsh", "wsl", "ffmpeg", "tailscale", "ollama", "claude", "git"):
            return which(n) is not None
        if n == "notify":
            return which("powershell") is not None
        if n == "psutil":
            return has_psutil()
        return which(n) is not None
    # Linux : comportement historique = fonctionnalités actives (pas de régression)
    if n in ("tmux", "gnome-terminal", "journalctl", "arecord", "docker", "loginctl",
             "systemctl", "xdg-open", "notify-send", "tailscale", "ollama", "claude", "git", "ffmpeg"):
        return shutil.which(n) is not None
    if n == "systemd":
        return shutil.which("systemctl") is not None
    if n == "cuda":
        return shutil.which("nvidia-smi") is not None
    if n == "whisper_local":
        return importlib.util.find_spec("faster_whisper") is not None
    if n == "notify":
        return shutil.which("notify-send") is not None
    if n == "x11":
        return bool(os.environ.get("DISPLAY"))
    if n == "wayland":
        return bool(os.environ.get("WAYLAND_DISPLAY"))
    if n == "psutil":
        return has_psutil()
    if n in ("lumen", "flo", "appimage", "bash_scripts", "gitbash"):
        return True
    return shutil.which(n) is not None


def feature_available(name: str) -> bool:
    """Drapeaux mémoïsés : 'tmux', 'gnome-terminal', 'systemd', 'journalctl',
    'docker', 'arecord', 'lumen', 'flo', 'whisper_local', 'cuda', 'x11',
    'appimage', 'bash_scripts', 'gitbash', 'wt', 'powershell', 'wsl', 'notify'…
    Sous Windows tmux/systemd/journalctl/arecord/lumen/flo/x11/appimage/
    bash_scripts → False. Sert au setEnabled(False) + tooltip des boutons."""
    return _feature_cached(name or "")


# ═══════════════════════════════════════════════════════════════════════════
#  TÉLÉMÉTRIE SYSTÈME
# ═══════════════════════════════════════════════════════════════════════════

def gpu_info(timeout: float = 4.0) -> list[dict]:
    """nvidia-smi --query-gpu=name,memory.used,memory.total,utilization.gpu,
    temperature.gpu → [{index, name, used, total, util, temp, used_mb,
    total_mb, util_pct, temp_c}] ; [] si absent/erreur (jamais d'exception)."""
    exe = nvidia_smi_exe()
    if not exe:
        return []
    r = run_cmd([exe, "--query-gpu=name,memory.used,memory.total,utilization.gpu,temperature.gpu",
                 "--format=csv,noheader,nounits"], timeout=timeout)
    if r.returncode != 0 or not (r.stdout or "").strip():
        return []
    gpus = []
    for i, line in enumerate(r.stdout.strip().splitlines()):
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 5:
            continue

        def _int(x):
            try:
                return int(float(x))
            except ValueError:
                return 0
        used, total, util, temp = (_int(parts[1]), _int(parts[2]), _int(parts[3]), _int(parts[4]))
        gpus.append({"index": i, "name": parts[0], "used": used, "total": total, "util": util,
                     "temp": temp, "used_mb": used, "total_mb": total, "util_pct": util, "temp_c": temp})
    return gpus


def mem_info() -> dict:
    """RAM réelle : psutil.virtual_memory() → ctypes GlobalMemoryStatusEx
    (Windows) → /proc/meminfo → free -m. Clés (union des contrats) :
    total_mb, used_mb, avail_mb, free_mb, percent, total_gb, used_gb,
    total, used, free, available (Mo). Jamais de valeurs fictives silencieuses :
    dict vide-zéro avec 'error' si tout échoue."""
    tot = used = free = avail = None
    ps = _psutil()
    if ps is not None:
        try:
            vm = ps.virtual_memory()
            tot, avail, used, free = vm.total, vm.available, vm.used, vm.free
        except Exception:
            tot = None
    if tot is None and IS_WINDOWS:
        try:
            import ctypes

            class _MS(ctypes.Structure):
                _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                            ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                            ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                            ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                            ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
            ms = _MS()
            ms.dwLength = ctypes.sizeof(_MS)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(ms)):
                tot, avail = ms.ullTotalPhys, ms.ullAvailPhys
                free, used = avail, tot - avail
        except Exception:
            tot = None
    if tot is None and os.path.exists("/proc/meminfo"):
        try:
            vals = {}
            with open("/proc/meminfo") as fh:
                for line in fh:
                    k, _, v = line.partition(":")
                    vals[k.strip()] = int(v.split()[0]) * 1024
            tot, free = vals["MemTotal"], vals["MemFree"]
            avail = vals.get("MemAvailable", free)
            used = tot - avail
        except Exception:
            tot = None
    if tot is None and shutil.which("free"):
        r = run_cmd(["free", "-b"], timeout=3)
        for line in (r.stdout or "").splitlines():
            if line.startswith("Mem:"):
                p = line.split()
                tot, used, free = int(p[1]), int(p[2]), int(p[3])
                avail = int(p[6]) if len(p) > 6 else free
    if tot is None:
        return {"total_mb": 0, "used_mb": 0, "avail_mb": 0, "free_mb": 0, "percent": 0.0,
                "total_gb": 0.0, "used_gb": 0.0, "total": 0, "used": 0, "free": 0, "available": 0,
                "error": "mémoire : aucune source disponible"}
    mb = 1024 * 1024
    pct = round(used / tot * 100, 1) if tot else 0.0
    return {"total_mb": int(tot / mb), "used_mb": int(used / mb), "avail_mb": int(avail / mb),
            "free_mb": int(free / mb), "percent": pct, "total_gb": round(tot / mb / 1024, 1),
            "used_gb": round(used / mb / 1024, 1), "total": int(tot / mb), "used": int(used / mb),
            "free": int(free / mb), "available": int(avail / mb)}


def ram_info() -> dict:
    """Alias de mem_info() (clés de telemetry.get_ram_info incluses)."""
    return mem_info()


def get_mem_info_mb() -> dict:
    """Alias de mem_info() (clés total/used/free/available/percent incluses)."""
    return mem_info()


def get_cpu_temp_c() -> int | None:
    """Linux : max de /sys/class/thermal/thermal_zone*/temp ; Windows : None
    (pas de capteur fiable sans WMI/pilote) → l'UI affiche « n/d »."""
    if IS_WINDOWS:
        return None
    import glob
    temps = []
    for p in glob.glob("/sys/class/thermal/thermal_zone*/temp"):
        try:
            with open(p) as fh:
                v = fh.read().strip()
            if v.lstrip("-").isdigit():
                temps.append(int(v) / 1000.0)
        except OSError:
            continue
    return int(round(max(temps))) if temps else None


def cpu_info() -> dict:
    """Clés de telemetry.get_cpu_info (load_1m/5m/15m en str, temp_c,
    zram_percent, zram_used_mb) + percent, cores. Linux : /proc (inchangé) ;
    Windows : psutil (loadavg émulé, swap_memory pour le swap), temp_c=0.0."""
    ps = _psutil()
    loads = ["0.00", "0.00", "0.00"]
    if IS_LINUX and os.path.exists("/proc/loadavg"):
        try:
            with open("/proc/loadavg") as fh:
                loads = fh.read().split()[:3]
        except OSError:
            pass
    elif ps is not None:
        try:
            loads = [f"{x:.2f}" for x in ps.getloadavg()]
        except Exception:
            pass
    temp = get_cpu_temp_c() or 0.0
    zram_pct, zram_used = 0, 0
    if IS_LINUX and os.path.exists("/proc/swaps"):
        try:
            with open("/proc/swaps") as fh:
                for line in fh:
                    if "zram" in line or "partition" in line:
                        p = line.split()
                        tot_kb, used_kb = int(p[2]), int(p[3])
                        zram_used = round(used_kb / 1024, 1)
                        zram_pct = round(used_kb / tot_kb * 100, 1) if tot_kb else 0
        except (OSError, ValueError, IndexError):
            pass
    elif ps is not None:
        try:
            sw = ps.swap_memory()
            zram_used = round(sw.used / 1024 / 1024, 1)
            zram_pct = round(sw.percent, 1)
        except Exception:
            pass
    pct, cores = 0.0, os.cpu_count() or 1
    if ps is not None:
        try:
            pct = ps.cpu_percent(interval=None)
        except Exception:
            pass
    return {"load_1m": loads[0], "load_5m": loads[1], "load_15m": loads[2],
            "temp_c": float(temp), "zram_percent": zram_pct, "zram_used_mb": zram_used,
            "percent": pct, "cores": cores}


def disk_usage(path: str) -> tuple[int, int, int] | None:
    """(total, used, free) en octets via shutil.disk_usage ; None si absent/erreur."""
    try:
        if not path or not os.path.exists(path):
            return None
        du = shutil.disk_usage(path)
        return du.total, du.used, du.free
    except OSError:
        return None


def storage_mount_points() -> list[str]:
    """Linux → ['/', '/home/turbo', '/mnt/jarvis-m1', '/mnt/jarvis-m6', '/media/turbo']
    (inchangé) ; Windows → racines des lecteurs fixes (['C:\\\\', …])."""
    if not IS_WINDOWS:
        return ["/", "/home/turbo", "/mnt/jarvis-m1", "/mnt/jarvis-m6", "/media/turbo"]
    return [d["mountpoint"] for d in disk_usage_all() if d.get("mounted")]


def _fmt_size(n: int) -> str:
    for unit, div in (("T", 1024 ** 4), ("G", 1024 ** 3), ("M", 1024 ** 2), ("K", 1024)):
        if n >= div:
            v = n / div
            return f"{v:.0f}{unit}" if v >= 10 else f"{v:.1f}{unit}"
    return f"{n}B"


def disk_usage_all() -> list[dict]:
    """Partitions montées (psutil.disk_partitions(all=False), cdrom/indisponibles
    ignorés) → [{device, mountpoint, fstype, opts, total_gb, used_gb, free_gb,
    percent, mounted}]. Repli sans psutil : storage_mount_points() Linux / C:\\."""
    out = []
    ps = _psutil()
    parts = []
    if ps is not None:
        try:
            parts = [(p.device, p.mountpoint, p.fstype, p.opts) for p in ps.disk_partitions(all=False)]
        except Exception:
            parts = []
    if not parts:
        roots = ["C:\\"] if IS_WINDOWS else ["/", "/home", "/mnt", "/media"]
        parts = [(r, r, "", "") for r in roots if os.path.exists(r)]
    for device, mp, fstype, opts in parts:
        if "cdrom" in (opts or "").lower() or (fstype or "").lower() in ("iso9660", "udf", "squashfs"):
            continue
        du = disk_usage(mp)
        if du is None:
            continue
        tot, used, free = du
        gb = 1024 ** 3
        out.append({"device": device, "mountpoint": mp, "fstype": fstype, "opts": opts,
                    "total_gb": round(tot / gb, 1), "used_gb": round(used / gb, 1),
                    "free_gb": round(free / gb, 1),
                    "percent": round(used / tot * 100, 1) if tot else 0.0, "mounted": True})
    return out


def list_disks() -> list[dict]:
    """Schéma de inventaire.get_peripheriques()['disques'] : {nom, taille, type,
    montage, modele, usage}. Linux : lsblk -J (code historique) ; Windows :
    psutil.disk_partitions + disk_usage (nom='C:', modele=fstype+label).
    [] si indisponible."""
    if not IS_WINDOWS:
        r = run_cmd(["lsblk", "-J", "-o", "NAME,SIZE,TYPE,MOUNTPOINT,MODEL,FSUSE%"], timeout=6)
        if r.returncode != 0:
            return []
        disks = []
        try:
            def _plat(n, parent=None):
                if n.get("type") != "loop":
                    disks.append({"nom": n.get("name", ""), "taille": n.get("size", ""),
                                  "type": n.get("type", ""), "montage": n.get("mountpoint") or "",
                                  "modele": (n.get("model") or parent or "").strip(),
                                  "usage": n.get("fsuse%") or ""})
                for e in n.get("children", []):
                    _plat(e, parent=n.get("model"))
            for n in json.loads(r.stdout).get("blockdevices", []):
                _plat(n)
        except (json.JSONDecodeError, KeyError, AttributeError):
            return []
        return disks
    disks = []
    labels = _win_volume_labels()
    for d in disk_usage_all():
        mp = d["mountpoint"]
        letter = mp.rstrip("\\/")
        disks.append({"nom": letter, "taille": _fmt_size(int(d["total_gb"] * 1024 ** 3)),
                      "type": "part", "montage": mp,
                      "modele": " ".join(x for x in (d["fstype"], labels.get(mp.upper(), "")) if x).strip(),
                      "usage": f"{d['percent']:.0f}%"})
    return disks


def _win_volume_labels() -> dict[str, str]:
    """{'C:\\\\': 'Windows', …} via GetVolumeInformationW ; {} hors Windows."""
    if not IS_WINDOWS:
        return {}
    labels = {}
    try:
        import ctypes
        k32 = ctypes.windll.kernel32
        old = k32.SetErrorMode(0x0001 | 0x0002)
        try:
            mask = k32.GetLogicalDrives()
            for i in range(26):
                if not mask & (1 << i):
                    continue
                root = f"{chr(65 + i)}:\\"
                if k32.GetDriveTypeW(root) in (0, 1, 5):
                    continue
                buf = ctypes.create_unicode_buffer(261)
                if k32.GetVolumeInformationW(root, buf, 261, None, None, None, None, 0):
                    labels[root.upper()] = buf.value
        finally:
            k32.SetErrorMode(old)
    except Exception:
        pass
    return labels


def list_usb(timeout: float = 8) -> tuple[list[dict], str]:
    """({bus, device, id, libelle, hub}, raison). Linux : lsusb (historique) ;
    Windows : PowerShell Get-PnpDevice -Class USB (1-3 s : HORS thread GUI) ;
    id 'vid:pid' extrait de InstanceId, hub=True si 'Root Hub'/'Hub USB'."""
    if not IS_WINDOWS:
        r = run_cmd(["lsusb"], timeout=timeout)
        if r.returncode != 0:
            return [], (r.stderr or r.stdout or "lsusb indisponible").strip()
        out = []
        for l in (r.stdout or "").splitlines():
            if ": ID " not in l:
                continue
            tete, reste = l.split(": ID ", 1)
            m = tete.split()
            ident, _, libelle = reste.partition(" ")
            out.append({"bus": m[1] if len(m) > 1 else "", "device": m[3] if len(m) > 3 else "",
                        "id": ident, "libelle": libelle.strip(), "hub": "root hub" in l.lower()})
        return out, ""
    psh = which("powershell")
    if not psh:
        return [], "PowerShell indisponible"
    script = ("[Console]::OutputEncoding=[Text.Encoding]::UTF8; "
              "Get-PnpDevice -PresentOnly -Class USB | Select-Object FriendlyName,InstanceId | ConvertTo-Json -Compress")
    r = run_cmd([psh, "-NoProfile", "-NonInteractive", "-Command", script], timeout=timeout)
    if r.returncode != 0 or not (r.stdout or "").strip():
        return [], (r.stderr or "Get-PnpDevice a échoué").strip()[:200]
    try:
        data = json.loads(r.stdout)
    except json.JSONDecodeError:
        return [], "réponse PowerShell illisible"
    if isinstance(data, dict):
        data = [data]
    out = []
    for i, d in enumerate(data or []):
        inst = d.get("InstanceId") or ""
        lib = d.get("FriendlyName") or ""
        m = re.search(r"VID_([0-9A-Fa-f]{4})&PID_([0-9A-Fa-f]{4})", inst)
        ident = f"{m.group(1).lower()}:{m.group(2).lower()}" if m else ""
        out.append({"bus": "", "device": str(i + 1), "id": ident, "libelle": lib,
                    "hub": bool(re.search(r"root hub|hub usb|usb hub|concentrateur", lib, re.I))})
    return out, ""


def list_net_ifaces() -> list[dict]:
    """[{nom, etat, mac, adresses}] sans lo/veth/br-/docker (Linux, ip -br -j
    addr) ni Loopback*/vEthernet (WSL*/Default Switch) (Windows, psutil)."""
    if not IS_WINDOWS:
        r = run_cmd(["ip", "-br", "-j", "addr"], timeout=6)
        if r.returncode != 0:
            return []
        out = []
        try:
            for i in json.loads(r.stdout):
                nom = i.get("ifname", "")
                if nom == "lo" or nom.startswith(("veth", "br-", "docker")):
                    continue
                out.append({"nom": nom, "etat": i.get("operstate", ""), "mac": i.get("address", ""),
                            "adresses": [a.get("local", "") for a in i.get("addr_info", [])]})
        except (json.JSONDecodeError, AttributeError):
            return []
        return out
    ps = _psutil()
    if ps is None:
        return []
    try:
        addrs, stats = ps.net_if_addrs(), ps.net_if_stats()
    except Exception:
        return []
    out = []
    af_link = getattr(ps, "AF_LINK", getattr(socket, "AF_LINK", -1))
    for nom, lst in addrs.items():
        low = nom.lower()
        if low.startswith("loopback") or low.startswith("vethernet (wsl") or low == "vethernet (default switch)":
            continue
        mac, ips = "", []
        for a in lst:
            if a.family == af_link:
                mac = a.address
            elif a.family in (socket.AF_INET, socket.AF_INET6):
                ips.append(a.address.split("%")[0])
        st = stats.get(nom)
        out.append({"nom": nom, "etat": "UP" if (st and st.isup) else "DOWN", "mac": mac, "adresses": ips})
    return out


_PORTS_CACHE: tuple[float, frozenset] = (0.0, frozenset())
_PORTS_LOCK = threading.Lock()


def local_listening_ports(ttl: float = 1.0) -> set[int]:
    """Ports TCP en LISTEN sur la machine (psutil.net_connections, ~2 ms), cache
    ttl secondes. set() si psutil absent (l'appelant retombe sur connect())."""
    global _PORTS_CACHE
    ps = _psutil()
    if ps is None:
        return set()
    now = time.time()
    with _PORTS_LOCK:
        ts, cached = _PORTS_CACHE
        if now - ts < ttl:
            return set(cached)
        try:
            ports = frozenset(c.laddr.port for c in ps.net_connections(kind="tcp")
                              if c.status == ps.CONN_LISTEN and c.laddr)
        except Exception:
            return set(cached)
        _PORTS_CACHE = (now, ports)
        return set(ports)


def is_local_port_open(port: int, ttl: float = 1.0) -> bool:
    """Vrai si un serveur local écoute ``port`` (via local_listening_ports ;
    repli connect() 127.0.0.1 court si psutil manque)."""
    ports = local_listening_ports(ttl)
    if ports or has_psutil():
        return int(port) in ports
    try:
        with socket.create_connection(("127.0.0.1", int(port)), timeout=0.2):
            return True
    except OSError:
        return False


def tailscale_via_socks() -> bool:
    """True hors Windows (rig : sondes 100.x via SOCKS5 127.0.0.1:1055) ;
    False sous Windows (Tailscale natif : connect() direct)."""
    return not IS_WINDOWS


def _tailscale_probe() -> tuple[list[str] | None, str]:
    if IS_WINDOWS:
        exe = which("tailscale")
        return ([exe], "") if exe else (None, "tailscale absent")
    ts_bin = shutil.which("tailscale") or os.path.join(HOME, ".local", "bin", "tailscale")
    if not os.path.isfile(ts_bin):
        return None, "tailscale absent"
    for sock in ("/var/run/tailscale/tailscaled.sock", "/run/tailscale/tailscaled.sock",
                 os.path.join(HOME, ".config", "tailscale-state", "tailscaled.sock")):
        if os.path.exists(sock):
            return [ts_bin, "--socket", sock], ""
    return None, "démon tailscaled inactif (socket absent)"


def tailscale_cmd() -> list[str] | None:
    """Préfixe argv pour parler au démon Tailscale : Linux [bin, '--socket', sock]
    (premier socket existant) ; Windows [tailscale.exe] sans --socket (named
    pipe du service). None si absent → tailscale_reason() donne la raison."""
    return _tailscale_probe()[0]


def tailscale_reason() -> str:
    """Raison lisible quand tailscale_cmd() rend None ('' sinon)."""
    return _tailscale_probe()[1]


def list_scheduled_timers(keywords: tuple[str, ...] = ("jarvis", "locomotive", "board"),
                          timeout: float = 20.0) -> list[dict]:
    """Linux → systemctl --user list-timers (parse historique) ; Windows →
    Get-ScheduledTask (PowerShell, ~3 s) filtré sur keywords (() = toutes).
    Clés {next, left, unit, activates} (+ status/last sous Windows). [] si
    l'outil manque ; jamais d'exception."""
    kws = tuple(k.lower() for k in keywords)
    timers = []
    if IS_WINDOWS:
        # `schtasks /Query` met ~40 s sur ce PC ; Get-ScheduledTask filtré côté
        # PowerShell répond en ~3 s. Reste lent : à appeler HORS thread GUI.
        psh = which("powershell")
        if not psh:
            return []
        rx = "|".join(re.escape(k) for k in kws) or "."
        script = ("[Console]::OutputEncoding=[Text.Encoding]::UTF8; "
                  f"Get-ScheduledTask | Where-Object {{ $_.TaskName -match '{rx}' }} | ForEach-Object {{ "
                  "$i = $_ | Get-ScheduledTaskInfo; [pscustomobject]@{Name=$_.TaskName; Path=$_.TaskPath; "
                  "State=[string]$_.State; Next=[string]$i.NextRunTime; Last=[string]$i.LastRunTime} } "
                  "| ConvertTo-Json -Compress")
        r = run_cmd([psh, "-NoProfile", "-NonInteractive", "-Command", script], timeout=timeout)
        if r.returncode != 0 or not (r.stdout or "").strip():
            return []
        try:
            data = json.loads(r.stdout)
        except json.JSONDecodeError:
            return []
        if isinstance(data, dict):
            data = [data]
        for d in data or []:
            name = d.get("Name") or ""
            timers.append({"next": d.get("Next") or "", "left": "", "unit": name,
                           "activates": (d.get("Path") or "") + name, "status": d.get("State") or "",
                           "last": d.get("Last") or ""})
        return timers
    r = run_cmd(["systemctl", "--user", "list-timers", "--no-pager", "--no-legend"], timeout=8)
    for line in (r.stdout or "").splitlines():
        line = line.strip()
        if not line or (kws and not any(k in line.lower() for k in kws)):
            continue
        parts = line.split(maxsplit=6)
        if len(parts) >= 6:
            timers.append({"next": parts[0] + " " + parts[1] if len(parts) > 1 else parts[0],
                           "left": parts[2] if len(parts) > 2 else "",
                           "unit": parts[-2] if len(parts) >= 2 else parts[-1],
                           "activates": parts[-1]})
    return timers


def record_audio_wav(path: str, duration_s: int, rate: int = 16000) -> tuple[bool, str]:
    """Linux → arecord -D default -f S16_LE -r rate -c 1 -d dur ; Windows →
    ffmpeg -f dshow -i audio=<1er périphérique> ; sinon (False, message)."""
    duration_s = max(1, int(duration_s))
    if not IS_WINDOWS:
        if not shutil.which("arecord"):
            return False, "arecord introuvable (alsa-utils)"
        r = run_cmd(["arecord", "-D", "default", "-f", "S16_LE", "-r", str(rate), "-c", "1",
                     "-d", str(duration_s), path], timeout=duration_s + 10)
        return (r.returncode == 0), ("" if r.returncode == 0 else (r.stderr or "arecord a échoué").strip()[-300:])
    ffmpeg = which("ffmpeg")
    if not ffmpeg:
        return False, "Enregistrement micro indisponible sous Windows (ffmpeg/dshow absent)"
    probe = run_cmd([ffmpeg, "-hide_banner", "-list_devices", "true", "-f", "dshow", "-i", "dummy"], timeout=10)
    dev = None
    for line in (probe.stderr or "").splitlines():
        m = re.search(r'"([^"]+)"\s*\((audio)\)', line)
        if m:
            dev = m.group(1)
            break
    if not dev:
        return False, "Enregistrement micro indisponible sous Windows (aucun périphérique dshow audio)"
    r = run_cmd([ffmpeg, "-hide_banner", "-y", "-f", "dshow", "-i", f"audio={dev}", "-t", str(duration_s),
                 "-ar", str(rate), "-ac", "1", path], timeout=duration_s + 15)
    return (r.returncode == 0), ("" if r.returncode == 0 else (r.stderr or "ffmpeg a échoué").strip()[-300:])


# ═══════════════════════════════════════════════════════════════════════════
#  SESSION GRAPHIQUE
# ═══════════════════════════════════════════════════════════════════════════

def session_graphique() -> dict:
    """{'type', 'wayland', 'bureau'} : Windows → {'windows', False, 'Windows'}
    sans sous-processus ; Linux → XDG_* puis loginctl (logique historique de
    bureau_engine._session_graphique)."""
    if IS_WINDOWS:
        return {"type": "windows", "wayland": False, "bureau": "Windows"}
    typ = os.environ.get("XDG_SESSION_TYPE", "")
    bureau = os.environ.get("XDG_CURRENT_DESKTOP", "")
    if (not typ or not bureau) and shutil.which("loginctl"):
        try:
            sid = run_cmd(["loginctl", "list-sessions", "--no-legend"], timeout=4).stdout or ""
            sid = next((l.split()[0] for l in sid.splitlines() if " seat" in l or l.strip()), "")
            if sid:
                out = run_cmd(["loginctl", "show-session", sid, "-p", "Type", "-p", "Desktop"], timeout=4).stdout or ""
                vals = dict(l.split("=", 1) for l in out.splitlines() if "=" in l)
                typ = typ or vals.get("Type", "")
                bureau = bureau or vals.get("Desktop", "")
        except Exception:
            pass
    if not bureau and typ == "wayland" and os.path.exists("/run/user/1000/wayland-0"):
        bureau = "GNOME"
    return {"type": typ or "?", "wayland": typ == "wayland", "bureau": bureau or "?"}


def session_info() -> dict:
    """session_graphique() + {'desktop', 'user', 'platform'} : Windows →
    {'type': 'windows', 'desktop': 'explorer', 'wayland': False, 'user': …}."""
    try:
        user = getpass.getuser()
    except Exception:
        user = os.environ.get("USER") or os.environ.get("USERNAME") or "?"
    if IS_WINDOWS:
        return {"type": "windows", "desktop": "explorer", "bureau": "Windows",
                "wayland": False, "user": user, "platform": PLATFORM_NAME}
    s = session_graphique()
    s.update({"desktop": s.get("bureau", "?"), "user": user, "platform": PLATFORM_NAME})
    return s


# ═══════════════════════════════════════════════════════════════════════════
#  SQLITE PORTABLE (remplace le CLI sqlite3)
# ═══════════════════════════════════════════════════════════════════════════

def sqlite_schema_dump(db_path: str, out_path: str) -> int:
    """`sqlite3 db .schema > out` en pur Python : écrit les CREATE en UTF-8,
    rend le nombre d'objets (0 et fichier vide si la base est illisible)."""
    n = 0
    lines = []
    try:
        con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=3.0)
        try:
            for (sql,) in con.execute("SELECT sql FROM sqlite_master WHERE sql IS NOT NULL ORDER BY type, name"):
                lines.append(sql.strip() + ";")
                n += 1
        finally:
            con.close()
    except sqlite3.Error:
        pass
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + ("\n" if lines else ""))
    return n


def sqlite_export_csv(db_path: str, sql: str, out_path: str) -> int:
    """`sqlite3 -header -csv db 'SQL' > out` en pur Python ; rend le nombre de
    lignes (0 si erreur SQL, fichier vide écrit)."""
    n = 0
    with open(out_path, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        try:
            con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=3.0)
            try:
                cur = con.execute(sql)
                if cur.description:
                    w.writerow([d[0] for d in cur.description])
                for row in cur:
                    w.writerow(row)
                    n += 1
            finally:
                con.close()
        except sqlite3.Error:
            return n
    return n


def find_sqlite_databases(root: str, max_depth: int = 3, min_size: int = 1024,
                          exclude_dirs: tuple[str, ...] = ("backup", "backups", "archive", "old", "corbeille")) -> list[str]:
    """`find root -maxdepth 3 -name '*.db' -size +1k | grep -v backups… | sort -u`
    portable via os.walk borné. Chemins absolus triés."""
    found = set()
    root = os.path.abspath(root)
    if not os.path.isdir(root):
        return []
    excl = {e.lower() for e in exclude_dirs}
    base_depth = root.rstrip(os.sep).count(os.sep)
    for dirpath, dirnames, filenames in os.walk(root):
        depth = dirpath.rstrip(os.sep).count(os.sep) - base_depth
        dirnames[:] = [d for d in dirnames if d.lower() not in excl]
        if depth >= max_depth - 1:
            dirnames[:] = []
        for f in filenames:
            if f.lower().endswith(".db"):
                p = os.path.join(dirpath, f)
                try:
                    if os.path.getsize(p) > min_size:
                        found.add(p)
                except OSError:
                    continue
    return sorted(found)


# ═══════════════════════════════════════════════════════════════════════════
#  PROCESSUS COURANT : stdio, excepthook, AppUserModelID, polices, notifications
# ═══════════════════════════════════════════════════════════════════════════

def ensure_utf8_stdio() -> None:
    """sys.stdout/sys.stderr.reconfigure(encoding='utf-8', errors='replace') si
    présents (pythonw → None : no-op). Évite UnicodeEncodeError 'charmap' sur
    les print() avec emoji quand stdout est un fichier/pipe cp1252."""
    for name in ("stdout", "stderr"):
        stream = getattr(sys, name, None)
        if stream is None:
            continue
        try:
            if hasattr(stream, "reconfigure"):
                stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def _log_err(msg: str) -> None:
    try:
        if sys.stderr is not None:
            sys.stderr.write(f"[platform_compat] {msg}\n")
            sys.stderr.flush()
    except Exception:
        pass


_EXCEPTHOOK_INSTALLED = False


def install_excepthook(log_path: str | None = None) -> str:
    """Installe sys.excepthook + threading.excepthook qui journalisent la
    traceback dans ``log_path`` (défaut JARVIS_DIR/logs/cockpit_gui.log) et sur
    stderr au lieu de laisser PyQt6 appeler qFatal() → abort (exit 9 sous
    Windows). Idempotent ; rend le chemin du journal."""
    global _EXCEPTHOOK_INSTALLED
    path = log_path or os.path.join(LOGS_DIR_DEFAULT, "cockpit_gui.log")

    def _write(text: str) -> None:
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "a", encoding="utf-8", errors="replace") as fh:
                fh.write(f"\n=== {time.strftime('%Y-%m-%d %H:%M:%S')} ===\n{text}")
        except Exception:
            pass
        try:
            if sys.stderr is not None:
                sys.stderr.write(text)
                sys.stderr.flush()
        except Exception:
            pass

    def _hook(exc_type, exc, tb):
        _write("".join(traceback.format_exception(exc_type, exc, tb)))

    def _thread_hook(args):
        _write("".join(traceback.format_exception(args.exc_type, args.exc_value, args.exc_traceback)))

    if not _EXCEPTHOOK_INSTALLED:
        sys.excepthook = _hook
        try:
            threading.excepthook = _thread_hook
        except Exception:
            pass
        _EXCEPTHOOK_INSTALLED = True
    return path


def set_windows_app_id(app_id: str = "Jarvis.Cockpit.OS") -> bool:
    """SetCurrentProcessExplicitAppUserModelID sous Windows (icône et
    regroupement propres dans la barre des tâches) ; no-op ailleurs. À appeler
    AVANT QApplication."""
    if not IS_WINDOWS:
        return False
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
        return True
    except Exception:
        return False


@functools.lru_cache(maxsize=1)
def _cascadia_present() -> bool:
    if not IS_WINDOWS:
        return False
    cands = [os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "Fonts"),
             os.path.join(os.environ.get("LOCALAPPDATA", ""), r"Microsoft\Windows\Fonts")]
    for d in cands:
        try:
            for f in os.listdir(d):
                if f.lower().startswith("cascadiamono") or f.lower().startswith("cascadiacode"):
                    return True
        except OSError:
            continue
    return False


def ui_font_family(mono: bool = False) -> str:
    """Famille de police : Linux → 'Ubuntu' / 'JetBrains Mono' (inchangé) ;
    Windows → 'Segoe UI' / 'Cascadia Mono' (repli 'Consolas')."""
    if IS_WINDOWS:
        if mono:
            return "Cascadia Mono" if _cascadia_present() else "Consolas"
        return "Segoe UI"
    return "JetBrains Mono" if mono else "Ubuntu"


def ui_font(mono: bool = False) -> str:
    """Alias de ui_font_family()."""
    return ui_font_family(mono)


def mono_font_family() -> str:
    return ui_font_family(mono=True)


def default_lmstudio_host() -> str:
    """JARVIS_LMSTUDIO_HOST si posée ; sinon '127.0.0.1' sous Windows (LM Studio
    local) et '192.168.42.241' ailleurs (tether du rig, inchangé)."""
    env = os.environ.get("JARVIS_LMSTUDIO_HOST", "").strip()
    if env:
        return env
    return "127.0.0.1" if IS_WINDOWS else "192.168.42.241"


_TOAST_PS = r"""
$ErrorActionPreference = 'SilentlyContinue'
$title = $env:JARVIS_NOTIFY_TITLE; $msg = $env:JARVIS_NOTIFY_MSG
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null
$t = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02)
$n = $t.GetElementsByTagName('text')
$n.Item(0).AppendChild($t.CreateTextNode($title)) | Out-Null
$n.Item(1).AppendChild($t.CreateTextNode($msg)) | Out-Null
$toast = [Windows.UI.Notifications.ToastNotification]::new($t)
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('JARVIS Cockpit').Show($toast)
"""


def notify(title: str, message: str = "", timeout_ms: int = 5000) -> bool:
    """Notification bureau : Linux → notify-send ; Windows → toast PowerShell
    (asynchrone, sans fenêtre) ; repli print(). Ne lève jamais."""
    title, message = str(title or "JARVIS"), str(message or "")
    try:
        if IS_WINDOWS:
            psh = which("powershell")
            if psh:
                env = dict(os.environ, JARVIS_NOTIFY_TITLE=title, JARVIS_NOTIFY_MSG=message)
                popen_detached([psh, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                                "-Command", _TOAST_PS], env=env)
                return True
        elif shutil.which("notify-send"):
            popen_detached(["notify-send", "-t", str(int(timeout_ms)), "-a", "JARVIS Cockpit", title, message])
            return True
    except Exception as e:
        _log_err(f"notify : {type(e).__name__}: {e}")
    try:
        print(f"[notification] {title} — {message}")
    except Exception:
        pass
    return False

