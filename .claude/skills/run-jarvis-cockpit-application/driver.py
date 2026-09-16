#!/usr/bin/env python3
"""
driver.py — harnais programmatique du cockpit PyQt6 (JARVIS Cockpit).

Instancie la vraie fenêtre (JarvisMasterCockpitWindow, 17 pages) SANS écran :
QT_QPA_PLATFORM=offscreen par défaut, captures via QWidget.grab(). Fonctionne
avec le Python Windows (.venv) comme avec un venv Linux/WSL.

  driver.py smoke [--out DIR] [--strict]     toutes les pages → PNG + bilan JSON
  driver.py repl                              REPL (stdin) : tabs / go / buttons /
                                              click / text / ss / wait / eval / quit
  driver.py -c "go 4" -c "buttons" -c "ss x.png"   commandes en une passe

Options communes : --show (fenêtre réelle : WSLg / bureau Windows au lieu de
offscreen), --home DIR (JARVIS_HOME), --settle MS (temps d'événements après
chaque commande, défaut 400).

Tout dialogue modal (QMessageBox…) ouvert par un clic est FERMÉ automatiquement
et son texte est rapporté : le driver ne bloque jamais sur une boîte de dialogue.
"""
from __future__ import annotations

import argparse
import json
import os
import queue
import sys
import threading
import time
import traceback
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent
RACINE = SKILL_DIR.parents[2]          # <unit>/.claude/skills/run-…/driver.py → <unit>
COCKPIT = RACINE / "cockpit"


def _preparer_environnement(home: str | None, show: bool) -> str:
    """Même préparation que jarvis_cockpit_launcher.pyw, plus le mode offscreen."""
    if home:
        os.environ["JARVIS_HOME"] = home
    if not os.environ.get("JARVIS_HOME"):
        base = os.environ.get("USERPROFILE") or os.path.expanduser("~")
        os.environ["JARVIS_HOME"] = os.path.join(base, "jarvis")
    for sous in ("logs", "data", "databases", "board", "cockpit"):
        os.makedirs(os.path.join(os.environ["JARVIS_HOME"], sous), exist_ok=True)
    if not show:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        if sys.platform == "win32":
            # Le plugin offscreen utilise la base de polices FreeType : sans ce
            # dossier, tout le texte des captures est en « tofu » (□□□).
            os.environ.setdefault("QT_QPA_FONTDIR",
                                  os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts"))
    os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")
    os.environ.setdefault("PYTHONUTF8", "1")
    os.chdir(RACINE)
    if str(COCKPIT) not in sys.path:
        sys.path.insert(0, str(COCKPIT))
    for flux in (sys.stdout, sys.stderr):
        try:
            flux.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    return os.environ["JARVIS_HOME"]


class Driver:
    def __init__(self, settle_ms: int = 400, out_dir: str | None = None):
        from PyQt6.QtCore import QTimer, qInstallMessageHandler
        from PyQt6.QtWidgets import QApplication
        import gui_app  # cockpit/gui_app.py

        def _filtre_qt(mode, ctx, msg):
            # Offscreen + C:\Windows\Fonts : chaque police .fon/variable non chargeable
            # crache « QFontEngineFT: Failed to create FreeType font engine ». Inoffensif.
            if "QFontEngineFT" in msg or "propagateSizeHints" in msg:
                return
            print(f"[qt] {msg}", file=sys.stderr, flush=True)
        qInstallMessageHandler(_filtre_qt)

        # Ne pas voler le canal d'instance unique d'un cockpit déjà ouvert.
        gui_app.IPC_SOCKET_NAME = f"jarvis_cockpit_driver_{os.getpid()}"
        self.gui_app = gui_app
        self.settle_ms = settle_ms
        self.out_dir = Path(out_dir or os.path.join(
            os.environ.get("TEMP") or os.environ.get("TMPDIR") or "/tmp", "jarvis-cockpit-driver"))
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.dialogs: list[dict] = []          # dialogues modaux fermés automatiquement
        self.app = QApplication.instance() or QApplication([sys.argv[0]])
        self.app.setStyle("Fusion")
        t0 = time.time()
        self.win = gui_app.JarvisMasterCockpitWindow()
        self.win.resize(1400, 900)
        self.win.show()
        self.wait(self.settle_ms)
        self.build_seconds = round(time.time() - t0, 2)
        # Chien de garde des dialogues modaux (toutes les 150 ms).
        self._dlg_timer = QTimer(self.win)
        self._dlg_timer.timeout.connect(self._fermer_dialogues)
        self._dlg_timer.start(150)

    # ── utilitaires ────────────────────────────────────────────────────────
    def wait(self, ms: int | None = None):
        """Fait tourner la boucle d'événements pendant ms (timers, threads, repaint)."""
        from PyQt6.QtCore import QEventLoop, QTimer
        loop = QEventLoop()
        QTimer.singleShot(self.settle_ms if ms is None else int(ms), loop.quit)
        loop.exec()

    def _fermer_dialogues(self):
        from PyQt6.QtWidgets import QApplication, QMessageBox, QDialog
        w = QApplication.activeModalWidget()
        if w is None:
            return
        info = {"classe": type(w).__name__, "titre": w.windowTitle()}
        if isinstance(w, QMessageBox):
            info["texte"] = w.text()
        self.dialogs.append(info)
        print(f"[driver] dialogue fermé automatiquement : {json.dumps(info, ensure_ascii=False)}", flush=True)
        if isinstance(w, QDialog):
            w.reject()
        else:
            w.close()

    def tabs(self) -> list[dict]:
        out = []
        for i, (widget, titre) in enumerate(self.win.tab_list):
            indisponible = isinstance(widget, self.gui_app._OngletIndisponible)
            out.append({"index": i, "titre": titre, "classe": type(widget).__name__,
                        "indisponible": indisponible})
        return out

    def go(self, cible: str):
        """cible = index ou sous-chaîne (insensible à la casse) du titre."""
        idx = None
        if cible.strip().isdigit():
            idx = int(cible)
        else:
            c = cible.strip().lower()
            for i, (widget, titre) in enumerate(self.win.tab_list):
                if c in titre.lower() or c in type(widget).__name__.lower():
                    idx = i
                    break
        if idx is None or not (0 <= idx < len(self.win.tab_list)):
            raise ValueError(f"onglet introuvable : {cible!r}")
        self.win.sidebar.setCurrentRow(idx)
        self.wait()
        return {"index": idx, "titre": self.win.tab_list[idx][1]}

    def page(self):
        return self.win.pages.currentWidget()

    def buttons(self) -> list[dict]:
        from PyQt6.QtWidgets import QAbstractButton
        out = []
        for b in self.page().findChildren(QAbstractButton):
            if not b.isVisibleTo(self.page()):
                continue
            out.append({"texte": b.text(), "actif": b.isEnabled(),
                        "classe": type(b).__name__, "infobulle": b.toolTip()})
        return out

    def click(self, texte: str) -> dict:
        from PyQt6.QtWidgets import QAbstractButton
        cands = [b for b in self.page().findChildren(QAbstractButton) if b.isVisibleTo(self.page())]
        exact = [b for b in cands if b.text() == texte]
        sub = [b for b in cands if texte.lower() in b.text().lower()]
        b = (exact or sub or [None])[0]
        if b is None:
            raise ValueError(f"bouton introuvable : {texte!r} (voir 'buttons')")
        if not b.isEnabled():
            return {"bouton": b.text(), "clique": False, "raison": "désactivé", "infobulle": b.toolTip()}
        avant = len(self.dialogs)
        b.click()
        self.wait()
        return {"bouton": b.text(), "clique": True, "dialogues": self.dialogs[avant:]}

    def text(self, limite: int = 4000) -> str:
        """Texte visible de la page courante (labels, zones de texte, tables)."""
        from PyQt6.QtWidgets import QLabel, QTextEdit, QPlainTextEdit, QTableWidget, QAbstractButton
        morceaux = []
        for w in self.page().findChildren((QLabel, QTextEdit, QPlainTextEdit, QTableWidget, QAbstractButton)):
            if not w.isVisibleTo(self.page()):
                continue
            if isinstance(w, QLabel):
                t = w.text()
            elif isinstance(w, (QTextEdit, QPlainTextEdit)):
                t = w.toPlainText()
            elif isinstance(w, QTableWidget):
                cellules = []
                for r in range(min(w.rowCount(), 40)):
                    ligne = [w.item(r, c).text() if w.item(r, c) else "" for c in range(w.columnCount())]
                    cellules.append(" | ".join(ligne))
                t = "\n".join(cellules)
            else:
                t = f"[{w.text()}]"
            t = t.strip()
            if t:
                morceaux.append(t)
        return "\n".join(morceaux)[:limite]

    def screenshot(self, chemin: str | None = None) -> str:
        if not chemin:
            idx = self.win.pages.currentIndex()
            chemin = str(self.out_dir / f"page-{idx:02d}.png")
        p = Path(chemin)
        if not p.is_absolute():
            p = self.out_dir / p
        p.parent.mkdir(parents=True, exist_ok=True)
        self.wait(150)
        ok = self.win.grab().save(str(p))
        if not ok:
            raise RuntimeError(f"capture échouée : {p}")
        return str(p)

    def smoke(self, strict: bool = False) -> int:
        bilan = {"construction_s": self.build_seconds, "pages": [], "dialogues": []}
        for t in self.tabs():
            self.go(str(t["index"]))
            png = self.screenshot()
            btns = self.buttons()
            t.update({"png": png, "boutons": len(btns),
                      "boutons_inactifs": [b["texte"] for b in btns if not b["actif"]][:12]})
            bilan["pages"].append(t)
            print(f"[{t['index']:2d}] {'KO ' if t['indisponible'] else 'ok '} {t['titre']:<34} "
                  f"{t['classe']:<22} {len(btns):3d} boutons  {png}", flush=True)
        bilan["dialogues"] = self.dialogs
        ko = [p["titre"] for p in bilan["pages"] if p["indisponible"]]
        bilan["pages_indisponibles"] = ko
        (self.out_dir / "smoke.json").write_text(json.dumps(bilan, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"\n{len(bilan['pages'])} pages, {len(ko)} indisponible(s) {ko}, "
              f"construction {self.build_seconds}s, bilan → {self.out_dir / 'smoke.json'}", flush=True)
        return 1 if (strict and ko) else 0

    # ── interpréteur de commandes ─────────────────────────────────────────
    def run_command(self, ligne: str):
        ligne = ligne.strip()
        if not ligne:
            return None
        cmd, _, arg = ligne.partition(" ")
        cmd = cmd.lower()
        if cmd in ("q", "quit", "exit"):
            raise SystemExit(0)
        if cmd == "tabs":
            return self.tabs()
        if cmd == "go":
            return self.go(arg)
        if cmd == "buttons":
            if arg:
                self.go(arg)
            return self.buttons()
        if cmd == "click":
            return self.click(arg)
        if cmd == "text":
            return self.text(int(arg) if arg.strip().isdigit() else 4000)
        if cmd in ("ss", "screenshot"):
            return self.screenshot(arg or None)
        if cmd == "wait":
            self.wait(int(arg or self.settle_ms))
            return "ok"
        if cmd == "dialogs":
            return self.dialogs
        if cmd == "eval":
            ns = {"d": self, "win": self.win, "app": self.app, "page": self.page()}
            return eval(arg, ns)  # noqa: S307 — porte de secours voulue
        if cmd == "smoke":
            return self.smoke("--strict" in arg)
        if cmd in ("help", "?"):
            return ("tabs | go <n|titre> | buttons [onglet] | click <texte> | text [n] | "
                    "ss [fichier.png] | wait [ms] | dialogs | eval <expr> | smoke | quit")
        raise ValueError(f"commande inconnue : {cmd!r} (help)")

    def repl(self):
        """Lit stdin dans un thread ; les commandes s'exécutent dans le thread Qt
        (boucle d'événements vivante entre deux commandes : timers, workers)."""
        from PyQt6.QtCore import QTimer
        q: queue.Queue = queue.Queue()

        def lecteur():
            for ligne in sys.stdin:
                q.put(ligne)
            q.put(None)

        threading.Thread(target=lecteur, daemon=True).start()
        print(f"[driver] prêt — captures dans {self.out_dir} — 'help' pour la liste", flush=True)
        print("> ", end="", flush=True)

        def pompe():
            try:
                ligne = q.get_nowait()
            except queue.Empty:
                return
            if ligne is None:
                self.app.quit()
                return
            try:
                res = self.run_command(ligne)
                if res is not None:
                    print(res if isinstance(res, str) else json.dumps(res, ensure_ascii=False, indent=1), flush=True)
            except SystemExit:
                self.app.quit()
                return
            except Exception as e:  # noqa: BLE001
                print(f"[erreur] {type(e).__name__}: {e}", flush=True)
            print("> ", end="", flush=True)

        timer = QTimer(self.win)
        timer.timeout.connect(pompe)
        timer.start(50)
        return self.app.exec()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mode", nargs="?", choices=["smoke", "repl"], default=None)
    ap.add_argument("-c", "--cmd", action="append", default=[], help="commande à exécuter (répétable)")
    ap.add_argument("--out", help="dossier des captures / smoke.json")
    ap.add_argument("--strict", action="store_true", help="smoke : code 1 si une page est indisponible")
    ap.add_argument("--show", action="store_true", help="vraie fenêtre (pas offscreen)")
    ap.add_argument("--home", help="JARVIS_HOME à utiliser")
    ap.add_argument("--settle", type=int, default=400, help="ms d'événements après chaque commande")
    a = ap.parse_args(argv)
    home = _preparer_environnement(a.home, a.show)
    print(f"[driver] racine={RACINE} JARVIS_HOME={home} QT_QPA_PLATFORM={os.environ.get('QT_QPA_PLATFORM', '(natif)')}", flush=True)
    try:
        d = Driver(settle_ms=a.settle, out_dir=a.out)
    except Exception:
        traceback.print_exc()
        return 2
    print(f"[driver] fenêtre construite en {d.build_seconds}s, {len(d.tabs())} pages", flush=True)
    code = 0
    for c in a.cmd:
        try:
            res = d.run_command(c)
            if res is not None:
                print(res if isinstance(res, str) else json.dumps(res, ensure_ascii=False, indent=1), flush=True)
        except SystemExit:
            break
        except Exception as e:  # noqa: BLE001
            print(f"[erreur] {c!r} → {type(e).__name__}: {e}", flush=True)
            code = 1
    if a.mode == "smoke":
        code = d.smoke(a.strict) or code
    elif a.mode == "repl":
        code = d.repl()
    d.win.close()
    return code


if __name__ == "__main__":
    sys.exit(main())
