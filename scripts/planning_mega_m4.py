#!/usr/bin/env python3
"""planning-mega.py — ÉNORME todolist dynamique UNIFIÉE (0-token), préchargée biblio.

Fusionne TOUTES les sources de tâches JARVIS en une seule file `pending`
consommable par le widget planning (:8899) et le routeur auto :

  1. BACKLOG BUSINESS  — objectifs de prod P0/P1 (load-backlog.py, 5 domaines :
                         facturation/prospection/infra/mirra/github). DURABLES :
                         ré-injectés tant qu'ils ne sont pas déjà pending.
  2. SCANS DYNAMIQUES  — incidents (health.log), TODO/FIXME code, projets Bureau
                         + cases `- [ ]`, repos git « sales » (planning-autogen.py).
  3. HEAVY TASKS       — titres des .md sous antigravity_heavy_tasks/backlog/.
  4. PRÉCHARGEMENT     — pour CHAQUE tâche, top bloc biblio (bloc.sh, BLOCS-INDEX
                         ~36k) attaché au contexte → « quoi faire + le bloc prêt ».

DÉDUP : contre la file PENDING courante uniquement (pas l'historique done).
        → la file se RECHARGE dès que le routeur /10min l'a drainée,
          et les objectifs business restent visibles jusqu'à résolution réelle.

0-token, stdlib uniquement (+ réutilise planning-autogen). Prévu pour timer + bouton widget.
Usage: planning-mega.py [--no-preload] [--dry]
"""

from __future__ import annotations

import ast
import importlib.util
import os
import re
import sqlite3
import sys
from pathlib import Path

HOME = Path.home()
DB = os.environ.get("JARVIS_DB", str(HOME / "jarvis" / "jarvis_master.db"))
BIN = HOME / "jarvis" / "bin"
LOAD_BACKLOG = BIN / "load-backlog.py"
PLANNING_AUTOGEN = BIN / "planning-autogen.py"
HEAVY_DIR = HOME / "jarvis" / "antigravity_heavy_tasks" / "backlog"
ULTRA_BACKLOG = HOME / "Workspaces" / "jarvis-linux" / "ULTRA_BACKLOG_400.md"

CAP_INSERT = 1200  # plafond par run (agrégat énorme : ultra-backlog + business + scans)
# au-delà de ce rang, on n'attache plus le bloc biblio (garde le run rapide sur gros volume)
PRELOAD_MAX = (
    int(os.environ.get("PLANNING_PRELOAD_MAX", "0")) or 0
)  # 0 = précharger tout

DOM_PRIO = {  # emoji d'affichage par priorité business
    "P0": "🔴",
    "P1": "🟠",
    "P2": "🟢",
}


def _load_module(path: Path, name: str):
    """Importe un fichier .py (nom avec tiret) sans l'exécuter comme script."""
    spec = importlib.util.spec_from_file_location(name, str(path))
    if not spec or not spec.loader:
        return None
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)  # définit fonctions/const, ne lance pas main()
        return mod
    except Exception:
        return None


# ─────────────────────── 1. backlog business ───────────────────────
def load_business_backlog() -> list[dict]:
    """Lit la constante BACKLOG de load-backlog.py par AST (aucun effet de bord)."""
    out: list[dict] = []
    try:
        tree = ast.parse(LOAD_BACKLOG.read_text())
    except Exception:
        return out
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(
            getattr(t, "id", "") == "BACKLOG" for t in node.targets
        ):
            try:
                entries = ast.literal_eval(node.value)
            except Exception:
                return out
            for dom, prio, title, fichier in entries:
                out.append(
                    {
                        "prio": DOM_PRIO.get(prio, "🟢"),
                        "dom": dom,
                        "title": title.strip(),
                        "src": f"backlog:{prio}",
                    }
                )
            break
    return out


# ─────────────────────── 2. scans dynamiques ───────────────────────
def load_dynamic_scans(mod) -> list[dict]:
    if not mod:
        return []
    out: list[dict] = []
    for fn in (
        "scan_incidents",
        "scan_git_dirty",
        "scan_bureau_projects",
        "scan_code_todos",
    ):
        f = getattr(mod, fn, None)
        if callable(f):
            try:
                for t in f():
                    t["src"] = fn
                    out.append(t)
            except Exception:
                pass
    return out


# ─────────────────────── 3. heavy tasks markdown ───────────────────────
def load_heavy_tasks() -> list[dict]:
    out: list[dict] = []
    if not HEAVY_DIR.exists():
        return out
    for md in sorted(HEAVY_DIR.glob("*.md")):
        try:
            lines = md.read_text(errors="ignore").splitlines()
        except Exception:
            continue
        label = md.stem[:30]
        for ln in lines:
            m = re.match(r"^\s*(?:-\s*\[ \]|#{1,3})\s+(.+)", ln)
            if m:
                txt = m.group(1).strip(" #").strip()
                if len(txt) > 6:
                    out.append(
                        {
                            "prio": "🟠",
                            "dom": "heavy",
                            "title": f"[{label}] {txt[:80]}",
                            "src": "heavy",
                        }
                    )
    return out


# ─────────────────────── 4. ULTRA-BACKLOG 400 (deep-research curé) ───────────────────────
def load_ultra_backlog() -> list[dict]:
    """Parse ULTRA_BACKLOG_400.md : 400 tâches curées, groupées par `## BLOC N : DOMAINE`.
    Le domaine est déduit du dernier titre de bloc rencontré ; chaque ligne numérotée
    `N. texte` devient une tâche routable préfixée par le domaine."""
    out: list[dict] = []
    if not ULTRA_BACKLOG.exists():
        return out
    try:
        lines = ULTRA_BACKLOG.read_text(errors="ignore").splitlines()
    except Exception:
        return out
    dom = "ultra"
    for ln in lines:
        h = re.match(r"^\s*#{1,3}\s*.*?BLOC\s*\d+\s*:\s*([^\(]+)", ln, re.I)
        if h:
            # domaine court, sans emoji ni parenthèses de plage
            d = re.sub(r"[^\wàâéèêîïôûüç &/-]", "", h.group(1)).strip().lower()
            dom = (d.split("&")[0].strip().replace(" ", "-") or "ultra")[:18]
            continue
        m = re.match(r"^\s*(\d+)\.\s+(.+)", ln)
        if m:
            txt = m.group(2).strip()
            if len(txt) > 6:
                out.append(
                    {
                        "prio": "🟠",
                        "dom": f"ub-{dom}",
                        "title": txt[:140],
                        "src": f"ultra:{m.group(1)}",
                    }
                )
    return out


# ─────────────────────── reports GitHub/audits (chronologie) ───────────────────────
AUDIT_RUNS = HOME / "jarvis" / "audit" / "runs"
# action STRUCTURÉE en début de ligne uniquement (évite les fragments mi-phrase)
_ACTION = re.compile(
    r"^\s*(?:[-*]\s*\[ \]|❌|⏳|▶|→|(?:prochaine action|à faire|todo|action)\s*:)\s*(.+)",
    re.I,
)


def load_reports_chronological(max_runs: int = 15, per_run: int = 6) -> list[dict]:
    """Lit les audits/reports datés les PLUS RÉCENTS (ordre chrono) et en extrait
    les actions concrètes → tâches planning taguées par date de report.
    Renforce la todolist depuis la lecture chronologique des reports GitHub/audits."""
    out: list[dict] = []
    if not AUDIT_RUNS.exists():
        return out
    # dossiers datés triés du plus récent au plus ancien (nom = AAAAMMJJ_HHMMSS_…)
    runs = sorted(
        [d for d in AUDIT_RUNS.iterdir() if d.is_dir()],
        key=lambda d: d.name,
        reverse=True,
    )[:max_runs]
    seen: set[str] = set()
    for run in runs:
        date = run.name[:8]  # AAAAMMJJ
        label = run.name[16:44] or run.name
        n = 0
        for md in sorted(run.glob("*.md")):
            try:
                lines = md.read_text(errors="ignore").splitlines()
            except Exception:
                continue
            for ln in lines:
                m = _ACTION.search(ln)
                if not m:
                    continue
                txt = m.group(1).strip(" *_#`").strip()
                # garde qualité : assez long, commence proprement (pas un fragment
                # mi-phrase minuscule), pas un lien, pas un doublon
                if len(txt) < 12 or txt.lower().startswith(
                    ("dans le", "http", "cela ", "et ")
                ):
                    continue
                if not (txt[0].isupper() or not txt[0].isalpha()):
                    continue
                key = txt.lower()[:60]
                if key in seen:
                    continue
                seen.add(key)
                out.append(
                    {
                        "prio": "🟠",
                        "dom": "report",
                        "title": f"[{date}·{label[:20]}] {txt[:80]}",
                        "src": f"report:{run.name[:15]}",
                    }
                )
                n += 1
                if n >= per_run:
                    break
            if n >= per_run:
                break
    return out


# ─────────────────────── ready_cmd (pour s'en servir) ───────────────────────
def ready_cmd(title: str, dom: str) -> str:
    """Suggère une commande PRÊTE à lancer selon le type de tâche → « quoi + comment »."""
    # git : "Committer/reviewer N fichiers dans REPO"
    if dom == "git":
        m = re.search(r"dans\s+([A-Za-z0-9._-]+)\s*$", title)
        if m:
            return (
                f'git -C "$(find ~ -maxdepth 4 -name {m.group(1)} -type d 2>/dev/null'
                ' | head -1)" status'
            )
    # incident : "... service SVC"
    if dom == "incident":
        m = re.search(r"service\s+([\w.@-]+)", title)
        if m:
            svc = m.group(1)
            return (
                f"systemctl --user status {svc}; "
                f"journalctl --user -u {svc} -n 30 --no-pager"
            )
    # code : "[fichier:ligne] KIND: ..."
    m = re.match(r"\[([^:\]]+):(\d+)\]", title)
    if m:
        f, ln = m.group(1), m.group(2)
        return (
            f"${{EDITOR:-nano}} +{ln} "
            f'"$(find ~/jarvis ~/labo ~/Bureau -name {f} 2>/dev/null | head -1)"'
        )
    return ""


# ─────────────────────── insertion ───────────────────────
def main(argv: list[str]) -> int:
    dry = "--dry" in argv
    preload = "--no-preload" not in argv

    autogen = _load_module(PLANNING_AUTOGEN, "planning_autogen")
    preload_fn = getattr(autogen, "preload_biblio", None) if autogen else None

    cands: list[dict] = []
    cands += load_business_backlog()
    # ULTRA_BACKLOG_400 est le foyer de BACKLOG_QUEUE.json (source `backlog` de
    # jarvis-plan.py) → ne PAS le réinjecter par défaut dans master (double compte).
    # Flag explicite --with-ultra pour l'inclure si on veut le voir dans le widget brut.
    if "--with-ultra" in argv:
        cands += load_ultra_backlog()
    cands += load_dynamic_scans(autogen)
    cands += load_heavy_tasks()
    cands += load_reports_chronological()

    c = sqlite3.connect(DB, timeout=15)
    c.execute("PRAGMA busy_timeout=15000")
    # dédup contre le PENDING courant uniquement → recharge après drain
    pending_titles = {
        r[0]
        for r in c.execute("SELECT title FROM tasks WHERE status='pending'").fetchall()
    }

    added = 0
    by_dom: dict[str, int] = {}
    seen = set(pending_titles)
    for t in cands:
        if added >= CAP_INSERT:
            break
        title = t["title"].strip()
        if not title or title in seen:
            continue
        seen.add(title)
        ctx = f"{t['prio']} [{t['dom']}] ({t.get('src', '?')})"
        do_preload = (
            preload
            and callable(preload_fn)
            and (PRELOAD_MAX == 0 or added < PRELOAD_MAX)
        )
        if do_preload:
            try:
                b = preload_fn(title)
                if b:
                    ctx += f" · biblio: {b}"
            except Exception:
                pass
        rc = ready_cmd(title, t["dom"])
        if rc:
            ctx += f" · ▶ {rc}"
        if not dry:
            c.execute(
                "INSERT INTO tasks(title, context, status, machine) "
                "VALUES(?,?,'pending','M1')",
                (title, ctx),
            )
        added += 1
        by_dom[t["dom"]] = by_dom.get(t["dom"], 0) + 1

    if not dry:
        c.commit()
    pending = c.execute("SELECT count(*) FROM tasks WHERE status='pending'").fetchone()[
        0
    ]
    c.close()

    tag = "DRY " if dry else ""
    print(
        f"[planning-mega] {tag}+{added} tâches (candidates={len(cands)}, "
        f"préchargées={preload}) · file pending={pending}"
    )
    for dom, n in sorted(by_dom.items(), key=lambda x: -x[1]):
        print(f"  {dom:14} +{n}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
