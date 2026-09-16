#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JARVIS COCKPIT — SYNCHRONISATION & AVANCEMENTS ENGINE
=====================================================
Agrégateur unifié et moteur d'orchestration :
  • Chantiers et tâches de production vivants (production.db)
  • Tâches maîtres et jalons (jarvis_master.db)
  • Statut des dépôts Git (branches, commits d'avance/retard, fichiers modifiés)
  • Timers et planification système (systemd user timers)
  • Actions de synchronisation bidirectionnelle, checkpoint WAL et journalisation
"""

import os
import time
import json
import sqlite3
import subprocess
from datetime import datetime

HOME = os.path.expanduser("~")
JARVIS_DIR = os.path.join(HOME, "jarvis")
PROD_DB = os.path.join(JARVIS_DIR, "data", "production.db")
MASTER_DB = os.path.join(JARVIS_DIR, "jarvis_master.db")
BOARD_DB = os.path.join(JARVIS_DIR, "board", "board.db")
PROSPECT_DB = os.path.join(JARVIS_DIR, "data", "prospection_reelle.db")
LOGS_DIR = os.path.join(JARVIS_DIR, "logs")
TASK_RESULTS_DIR = os.path.join(JARVIS_DIR, "data", "task_results")



def get_git_status() -> list:
    """Récupère l'état de synchronisation des dépôts Git principaux de JARVIS."""
    repos = [
        {"name": "jarvis-core", "path": JARVIS_DIR},
        {"name": "jarvis-cockpit-app", "path": os.path.join(HOME, "MOISSON", "github-repos", "jarvis-cockpit-application")},
        {"name": "pamerys-m4-cockpit", "path": os.path.join(HOME, "cockpit-app")}
    ]
    results = []
    for r in repos:
        p = r["path"]
        if not os.path.exists(os.path.join(p, ".git")):
            continue
        try:
            branch = subprocess.getoutput(f"git -C '{p}' rev-parse --abbrev-ref HEAD 2>/dev/null").strip()
            status_lines = subprocess.getoutput(f"git -C '{p}' status --porcelain 2>/dev/null").splitlines()
            modified = len([l for l in status_lines if l.strip()])
            last_commit = subprocess.getoutput(f"git -C '{p}' log -1 --format='%h - %s (%cr)' 2>/dev/null").strip()
            ahead_behind = subprocess.getoutput(f"git -C '{p}' rev-list --left-right --count HEAD...origin/{branch} 2>/dev/null").strip()
            ahead, behind = 0, 0
            if "\t" in ahead_behind or " " in ahead_behind:
                parts = ahead_behind.split()
                if len(parts) >= 2 and parts[0].isdigit() and parts[1].isdigit():
                    ahead, behind = int(parts[0]), int(parts[1])

            results.append({
                "name": r["name"],
                "path": p,
                "branch": branch or "main",
                "modified_files": modified,
                "ahead": ahead,
                "behind": behind,
                "last_commit": last_commit or "Aucun commit",
                "synced": (modified == 0 and ahead == 0 and behind == 0)
            })
        except Exception as e:
            results.append({
                "name": r["name"],
                "path": p,
                "branch": "inconnu",
                "modified_files": 0,
                "ahead": 0,
                "behind": 0,
                "last_commit": str(e),
                "synced": False
            })
    return results


def get_systemd_timers() -> list:
    """Lit les timers systemd actifs avec leurs cadences et prochaines exécutions."""
    timers = []
    try:
        cmd = "systemctl --user list-timers --no-pager --no-legend 2>/dev/null"
        out = subprocess.getoutput(cmd)
        for line in out.splitlines():
            line = line.strip()
            if not line or ("jarvis" not in line.lower() and "locomotive" not in line.lower() and "board" not in line.lower()):
                continue
            parts = line.split(maxsplit=6)
            if len(parts) >= 6:
                timers.append({
                    "next": parts[0] + " " + parts[1] if len(parts) > 1 else parts[0],
                    "left": parts[2] if len(parts) > 2 else "",
                    "unit": parts[-2] if len(parts) >= 2 else parts[-1],
                    "activates": parts[-1]
                })
    except Exception:
        pass
    return timers


def get_production_runs() -> list:
    """Récupère les chantiers de production et leurs sous-tâches depuis production.db."""
    if not os.path.exists(PROD_DB):
        return []
    try:
        con = sqlite3.connect(f"file:{PROD_DB}?mode=ro", uri=True, timeout=3.0)
        con.row_factory = sqlite3.Row
        cur = con.cursor()
        
        cur.execute("""
            SELECT run_id, besoin, COALESCE(famille, 'GENERAL') AS famille,
                   COALESCE(domaine, 'SYSTEM') AS domaine, etape, etat, ouvert_le, ferme_le
            FROM runs
            ORDER BY ouvert_le DESC
            LIMIT 25;
        """)
        runs_rows = cur.fetchall()
        
        runs = []
        for r in runs_rows:
            run_dict = dict(r)
            rid = run_dict["run_id"]
            
            cur.execute("""
                SELECT id, intitule, specialite, etat, livrable, preuve, cree_le, maj_le
                FROM taches
                WHERE run_id = ?
                ORDER BY rang ASC, id ASC;
            """, (rid,))
            taches = [dict(t) for t in cur.fetchall()]
            
            total_taches = len(taches)
            fait_taches = sum(1 for t in taches if t["etat"] == "fait")
            bloque_taches = sum(1 for t in taches if t["etat"] in ("bloque", "echec"))
            en_cours_taches = sum(1 for t in taches if t["etat"] == "en_cours")
            
            progress_pct = round((fait_taches / total_taches) * 100) if total_taches > 0 else 0
            if run_dict["etat"] == "livre":
                progress_pct = 100
                
            run_dict["taches"] = taches
            run_dict["total_taches"] = total_taches
            run_dict["fait_taches"] = fait_taches
            run_dict["bloque_taches"] = bloque_taches
            run_dict["en_cours_taches"] = en_cours_taches
            run_dict["progress_pct"] = progress_pct
            runs.append(run_dict)
            
        con.close()
        return runs
    except Exception:
        return []


def get_production_journal(limit: int = 15) -> list:
    """Récupère les derniers gestes consignés dans le journal unique de production."""
    if not os.path.exists(PROD_DB):
        return []
    try:
        con = sqlite3.connect(f"file:{PROD_DB}?mode=ro", uri=True, timeout=3.0)
        con.row_factory = sqlite3.Row
        cur = con.cursor()
        cur.execute("""
            SELECT id, horodate, niveau, brique, message, COALESCE(run_id, '') AS run_id
            FROM journal
            ORDER BY id DESC
            LIMIT ?;
        """, (limit,))
        rows = [dict(r) for r in cur.fetchall()]
        con.close()
        return rows
    except Exception:
        return []


def get_avancements_data() -> dict:
    """Agrège l'ensemble des données d'avancement et de synchronisation du système."""
    runs = get_production_runs()
    journal = get_production_journal(limit=12)
    git_repos = get_git_status()
    timers = get_systemd_timers()
    
    total_runs = len(runs)
    runs_ouverts = sum(1 for r in runs if r["etat"] == "ouvert")
    runs_livres = sum(1 for r in runs if r["etat"] == "livre")
    
    total_taches_all = sum(r["total_taches"] for r in runs)
    fait_taches_all = sum(r["fait_taches"] for r in runs)
    bloque_taches_all = sum(r["bloque_taches"] for r in runs)
    
    global_progress = round((fait_taches_all / total_taches_all) * 100) if total_taches_all > 0 else 100
    
    master_tasks_pending = 0
    master_tasks_done = 0
    if os.path.exists(MASTER_DB):
        try:
            con_m = sqlite3.connect(f"file:{MASTER_DB}?mode=ro", uri=True, timeout=2.0)
            c_m = con_m.cursor()
            # Le vocabulaire de statut de jarvis_master.db est en MAJUSCULES et varié
            # (COMPLETED, VALIDATED_BY_BOARD, IN_PROGRESS, PENDING…). On regroupe de
            # façon insensible à la casse pour ne plus renvoyer 0/0 à tort.
            _rows = c_m.execute(
                "SELECT UPPER(COALESCE(status,'')) AS s, COUNT(*) FROM tasks GROUP BY s"
            ).fetchall()
            _DONE = {"DONE", "COMPLETED", "VALIDATED_BY_BOARD", "LIVRE", "TERMINE", "TERMINÉ"}
            master_tasks_done = sum(n for s, n in _rows if s in _DONE)
            master_tasks_pending = sum(n for s, n in _rows if s not in _DONE)
            con_m.close()
        except Exception:
            pass

    contacts_prospectes = 0
    if os.path.exists(PROSPECT_DB):
        try:
            con_p = sqlite3.connect(f"file:{PROSPECT_DB}?mode=ro", uri=True, timeout=2.0)
            c_p = con_p.cursor()
            contacts_prospectes = c_p.execute("SELECT COUNT(*) FROM contacts_moissonnes").fetchone()[0]
            con_p.close()
        except Exception:
            pass
            
    return {
        "success": True,
        "timestamp": datetime.now().isoformat(),
        "kpis": {
            "runs_ouverts": runs_ouverts,
            "runs_livres": runs_livres,
            "total_runs": total_runs,
            "total_taches": total_taches_all,
            "fait_taches": fait_taches_all,
            "bloque_taches": bloque_taches_all,
            "global_progress": global_progress,
            "master_tasks_pending": master_tasks_pending,
            "master_tasks_done": master_tasks_done,
            "contacts_prospectes": contacts_prospectes
        },
        "runs": runs,
        "journal": journal,
        "git_repos": git_repos,
        "timers": timers
    }


def trigger_synchronisation(auto_git_commit: bool = False, message_commit: str = "") -> dict:
    """
    Exécute une synchronisation complète du système JARVIS :
      1. Checkpoint WAL sur toutes les bases SQLite actives.
      2. Snapshot horodaté d'avancement.
      3. Commit Git des avancées de code si demandé.
      4. Inscription dans le journal de production.
    """
    t0 = time.time()
    os.makedirs(LOGS_DIR, exist_ok=True)
    os.makedirs(TASK_RESULTS_DIR, exist_ok=True)
    
    actions_done = []
    
    dbs_to_checkpoint = [PROD_DB, MASTER_DB, BOARD_DB, PROSPECT_DB]
    for db in dbs_to_checkpoint:
        if os.path.exists(db):
            try:
                con = sqlite3.connect(db, timeout=5.0)
                con.execute("PRAGMA wal_checkpoint(PASSIVE);")
                con.commit()
                con.close()
                actions_done.append(f"WAL Checkpoint: {os.path.basename(db)}")
            except Exception as e:

                actions_done.append(f"WAL Checkpoint échoué ({os.path.basename(db)}): {e}")

    now_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    snap_file = os.path.join(TASK_RESULTS_DIR, f"sync_avancements_{now_str}.json")
    av_data = get_avancements_data()
    try:
        with open(snap_file, "w", encoding="utf-8") as f:
            json.dump(av_data, f, ensure_ascii=False, indent=2)
        actions_done.append(f"Snapshot créé: {os.path.basename(snap_file)}")
    except Exception as e:
        actions_done.append(f"Erreur snapshot: {e}")

    if os.path.exists(PROD_DB):
        try:
            con_p = sqlite3.connect(PROD_DB, timeout=5.0)
            con_p.execute("""
                INSERT INTO journal (horodate, niveau, brique, message, run_id)
                VALUES (datetime('now', 'localtime'), 'info', 'cockpit-sync', ?, '')
            """, (f"Synchronisation unifiée Cockpit ({len(actions_done)} opérations)",))
            con_p.commit()
            con_p.close()
            actions_done.append("Journal de production mis à jour")
        except Exception as e:
            actions_done.append(f"Journalisation échouée: {e}")

    if auto_git_commit:
        msg = message_commit or f"feat(sync): checkpoint avancements {now_str}"
        try:
            cmd_git = f"git -C '{JARVIS_DIR}' add -A && git -C '{JARVIS_DIR}' commit -m '{msg}' 2>/dev/null || true"
            subprocess.run(cmd_git, shell=True, capture_output=True, text=True, timeout=15)
            actions_done.append(f"Git commit effectué: {msg}")
        except Exception as e:
            actions_done.append(f"Erreur Git commit: {e}")

    elapsed = round(time.time() - t0, 3)
    return {
        "success": True,
        "elapsed_seconds": elapsed,
        "timestamp": datetime.now().isoformat(),
        "actions_done": actions_done,
        "summary": f"Synchronisation réussie en {elapsed}s ({len(actions_done)} actions réalisées)"
    }


def creer_nouveau_chantier(besoin: str, famille: str = "GENERAL", domaine: str = "SYSTEM") -> dict:
    """Crée un nouveau chantier de production et l'enregistre dans production.db."""
    if not besoin.strip():
        return {"success": False, "error": "Besoin vide"}
    
    if not os.path.exists(PROD_DB):
        return {"success": False, "error": "production.db introuvable"}
        
    run_id = datetime.now().strftime("%Y%m%d-%H%M%S") + f"-{int(time.time()*1000)%1000000:06d}"
    now_sql = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    try:
        con = sqlite3.connect(PROD_DB, timeout=5.0)
        cur = con.cursor()
        cur.execute("""
            INSERT INTO runs (run_id, besoin, famille, domaine, etape, etat, ouvert_le)
            VALUES (?, ?, ?, ?, 'detecter', 'ouvert', ?)
        """, (run_id, besoin.strip(), famille, domaine, now_sql))
        
        cur.execute("""
            INSERT INTO journal (horodate, niveau, brique, message, run_id)
            VALUES (?, 'info', 'prod-detecter', ?, ?)
        """, (now_sql, f"Chantier ouvert : {besoin.strip()[:60]}", run_id))
        
        cur.execute("""
            INSERT INTO taches (run_id, intitule, specialite, etat, cree_le)
            VALUES (?, ?, 'omega', 'pending', ?)
        """, (run_id, f"Initialisation & analyse : {besoin.strip()[:60]}", now_sql))
        
        con.commit()
        con.close()
        
        try:
            with open(os.path.join(JARVIS_DIR, "prod", ".run_courant"), "w") as f:
                f.write(run_id)
        except Exception:
            pass
            
        return {
            "success": True,
            "run_id": run_id,
            "message": f"Chantier {run_id} ouvert avec succès"
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def update_tache_production(tache_id: int, new_status: str) -> dict:
    """Met à jour le statut d'une tâche de production dans production.db."""
    if not os.path.exists(PROD_DB):
        return {"success": False, "error": "production.db introuvable"}
    try:
        now_sql = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        con = sqlite3.connect(PROD_DB, timeout=5.0)
        cur = con.cursor()
        cur.execute("""
            UPDATE taches
            SET etat = ?, maj_le = ?
            WHERE id = ?
        """, (new_status, now_sql, tache_id))
        
        cur.execute("""
            INSERT INTO journal (horodate, niveau, brique, message, run_id)
            VALUES (?, 'info', 'prod-tache', ?, '')
        """, (now_sql, f"Tâche #{tache_id} -> {new_status}"))
        
        con.commit()
        con.close()
        return {"success": True, "status": new_status}
    except Exception as e:
        return {"success": False, "error": str(e)}
