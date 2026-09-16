#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
jarvis_cockpit_launcher.pyw — Lanceur Windows de JARVIS Cockpit.

Cible des raccourcis crees par install.ps1 (execute via pythonw.exe : aucune
console). Sans argument il ouvre l'application PyQt6 ; avec --web le serveur
HTTP :8600 ; avec --tui le tableau de bord Textual dans une console.

Ce que fait ce lanceur, et pourquoi :
  * JARVIS_HOME  -> %USERPROFILE%\\jarvis si absent (dossier de donnees de
    l'application : logs, data, board, bases SQLite).
  * cwd          -> racine du depot, pour que les chemins relatifs tiennent.
  * sys.path     -> cockpit/ en tete, comme le fait gui_app.py lui-meme.
  * Journal      -> %JARVIS_HOME%\\logs\\cockpit-gui.log recoit stdout/stderr
    (pythonw.exe n'a pas de console : sans cela tout message est PERDU) et
    un sys.excepthook affiche la trace dans une QMessageBox. Un plantage est
    donc VISIBLE au lieu d'une fermeture silencieuse.

Sous Linux, ce fichier n'est pas utilise (les lanceurs .sh restent la voie
normale) mais il reste executable sans effet de bord.
"""

import os
import sys
import subprocess
import traceback
from datetime import datetime

RACINE = os.path.dirname(os.path.abspath(__file__))
COCKPIT = os.path.join(RACINE, "cockpit")
EST_WINDOWS = sys.platform == "win32"


def _preparer_environnement():
    """Variables et dossiers minimaux avant tout import de l'application."""
    if not os.environ.get("JARVIS_HOME"):
        base = os.environ.get("USERPROFILE") or os.path.expanduser("~")
        os.environ["JARVIS_HOME"] = os.path.join(base, "jarvis")
    home = os.environ["JARVIS_HOME"]
    for sous in ("logs", "data", "databases", "board", "cockpit"):
        try:
            os.makedirs(os.path.join(home, sous), exist_ok=True)
        except OSError:
            pass
    # Qt : mise a l'echelle DPI propre sur Windows, sans ecraser un choix utilisateur.
    os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")
    os.chdir(RACINE)
    if COCKPIT not in sys.path:
        sys.path.insert(0, COCKPIT)
    return home


def _ouvrir_journal(home):
    """Redirige stdout/stderr vers le journal (indispensable sous pythonw)."""
    chemin = os.path.join(home, "logs", "cockpit-gui.log")
    try:
        # Rotation rudimentaire : au-dela de 2 Mo on repart de zero.
        if os.path.isfile(chemin) and os.path.getsize(chemin) > 2 * 1024 * 1024:
            os.replace(chemin, chemin + ".1")
        fh = open(chemin, "a", encoding="utf-8", errors="replace", buffering=1)
    except OSError:
        return None
    fh.write(f"\n===== {datetime.now():%Y-%m-%d %H:%M:%S} lancement {sys.argv[1:] or ['gui']} "
             f"(py {sys.version.split()[0]}) =====\n")
    # Sous pythonw.exe, sys.stdout/sys.stderr valent None : on les remplace.
    # En console (JARVIS-Cockpit.cmd) on garde aussi l'affichage a l'ecran.
    class _Double:
        def __init__(self, *flux):
            self._flux = [f for f in flux if f is not None]

        def write(self, s):
            for f in self._flux:
                try:
                    f.write(s)
                except Exception:
                    pass
            return len(s)

        def flush(self):
            for f in self._flux:
                try:
                    f.flush()
                except Exception:
                    pass

        def isatty(self):
            return False

        def fileno(self):
            return fh.fileno()

    sys.stdout = _Double(sys.__stdout__, fh)
    sys.stderr = _Double(sys.__stderr__, fh)
    return chemin


def _afficher_erreur(titre, texte):
    """Boite de dialogue Qt si possible, sinon MessageBox Win32, sinon rien."""
    try:
        from PyQt6.QtWidgets import QApplication, QMessageBox
        app = QApplication.instance() or QApplication(sys.argv)
        boite = QMessageBox()
        boite.setIcon(QMessageBox.Icon.Critical)
        boite.setWindowTitle(titre)
        boite.setText("JARVIS Cockpit s'est arrete sur une erreur.\n"
                      "Le detail complet est dans le journal indique ci-dessous.")
        boite.setDetailedText(texte)
        boite.setStandardButtons(QMessageBox.StandardButton.Ok)
        boite.exec()
        return
    except Exception:
        pass
    if EST_WINDOWS:
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(None, texte[-3000:], titre, 0x10)
        except Exception:
            pass


def _installer_excepthook(journal):
    def hook(type_, valeur, tb):
        texte = "".join(traceback.format_exception(type_, valeur, tb))
        try:
            sys.stderr.write(texte)
            sys.stderr.flush()
        except Exception:
            pass
        if journal:
            texte += f"\n\nJournal : {journal}"
        _afficher_erreur("JARVIS Cockpit - erreur fatale", texte)

    sys.excepthook = hook


def _lancer_gui():
    import gui_app  # cockpit/gui_app.py — ajoute deja cockpit/ a sys.path
    gui_app.main()


def _lancer_web():
    # Le serveur ecrit sur stdout : sous pythonw il part dans le journal.
    import serveur  # cockpit/serveur.py
    serveur.main()


def _python_console():
    """python.exe du venv (pas pythonw) pour les modes qui exigent une console."""
    exe = sys.executable
    if EST_WINDOWS and exe.lower().endswith("pythonw.exe"):
        candidat = exe[:-len("pythonw.exe")] + "python.exe"
        if os.path.isfile(candidat):
            exe = candidat
    return exe


def _lancer_tui():
    """Textual a besoin d'un vrai terminal : Windows Terminal, sinon cmd."""
    script = os.path.join(COCKPIT, "app.py")
    if not EST_WINDOWS:
        os.execv(_python_console(), [_python_console(), script])
    py = _python_console()
    env = dict(os.environ)
    if _est_dans_console():
        # Deja en console (JARVIS-Cockpit.cmd --tui) : on execute sur place.
        raise SystemExit(subprocess.call([py, script], cwd=RACINE, env=env))
    import shutil
    wt = shutil.which("wt.exe")
    if wt:
        cmd = [wt, "-d", RACINE, "--title", "JARVIS Cockpit TUI", py, script]
    else:
        cmd = ["cmd.exe", "/c", "start", "JARVIS Cockpit TUI", "/D", RACINE, py, script]
    subprocess.Popen(cmd, cwd=RACINE, env=env)


def _est_dans_console():
    if not EST_WINDOWS:
        return True
    try:
        import ctypes
        return ctypes.windll.kernel32.GetConsoleWindow() != 0
    except Exception:
        return False


def _aide():
    print(__doc__)
    print("Options : (aucune) GUI PyQt6 | --web serveur :8600 | --tui console Textual | --help")


def main():
    home = _preparer_environnement()
    journal = _ouvrir_journal(home)
    _installer_excepthook(journal)
    args = [a.lower() for a in sys.argv[1:]]
    if "--help" in args or "-h" in args:
        _aide()
        return
    if "--web" in args or "-w" in args:
        _lancer_web()
    elif "--tui" in args or "-t" in args:
        _lancer_tui()
    else:
        _lancer_gui()


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except BaseException:
        # Une exception levee ICI (avant/hors boucle Qt) passe par le meme
        # chemin que sys.excepthook : journal + boite de dialogue.
        sys.excepthook(*sys.exc_info())
        sys.exit(1)
