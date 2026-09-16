#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JARVIS COCKPIT — NOTION BACKUP & VAULT ENGINE
==============================================
Gestionnaire des sauvegardes Notion, pages Markdown, tables CSV et schémas SQL :
  • Inventaire des pages Notion mémorisées
  • Consultation des tables CSV et schémas relationnels
  • Déclenchement de snapshot de sauvegarde 1-clic
"""

import os
import glob
import time
import subprocess
from datetime import datetime
from .platform_compat import IS_WINDOWS, desktop_dir, sqlite_schema_dump, sqlite_export_csv

# Linux : ~/Bureau (inchangé) ; Windows : le vrai dossier Bureau (~\Desktop, affiché « Bureau »)
if IS_WINDOWS:
    NOTION_DIR = os.path.join(desktop_dir(), "NOTION_JARVIS_BACKUP")
else:
    NOTION_DIR = os.path.expanduser("~/Bureau/NOTION_JARVIS_BACKUP")
MARKDOWN_DIR = os.path.join(NOTION_DIR, "notion_pages_markdown")
CSV_DIR = os.path.join(NOTION_DIR, "csv_tables")
SCHEMAS_DIR = os.path.join(NOTION_DIR, "sql_schemas")
SCRIPTS_DIR = os.path.join(NOTION_DIR, "scripts_backup")


def get_notion_stats() -> dict:
    """Récupère les statistiques et l'inventaire des sauvegardes Notion."""
    if not os.path.exists(NOTION_DIR):
        return {"exists": False, "pages": [], "csvs": [], "schemas": [], "scripts_count": 0}
        
    md_files = []
    if os.path.exists(MARKDOWN_DIR):
        for f in glob.glob(os.path.join(MARKDOWN_DIR, "*.md")):
            sz = os.path.getsize(f)
            md_files.append({
                "name": os.path.basename(f),
                "path": f,
                "size_kb": round(sz / 1024, 1),
                "mtime": datetime.fromtimestamp(os.path.getmtime(f)).strftime("%Y-%m-%d %H:%M")
            })

    csv_files = []
    if os.path.exists(CSV_DIR):
        for f in glob.glob(os.path.join(CSV_DIR, "*.csv")):
            sz = os.path.getsize(f)
            csv_files.append({
                "name": os.path.basename(f),
                "path": f,
                "size_kb": round(sz / 1024, 1),
                "mtime": datetime.fromtimestamp(os.path.getmtime(f)).strftime("%Y-%m-%d %H:%M")
            })

    sql_files = []
    if os.path.exists(SCHEMAS_DIR):
        for f in glob.glob(os.path.join(SCHEMAS_DIR, "*.sql")):
            sz = os.path.getsize(f)
            sql_files.append({
                "name": os.path.basename(f),
                "path": f,
                "size_kb": round(sz / 1024, 1),
                "mtime": datetime.fromtimestamp(os.path.getmtime(f)).strftime("%Y-%m-%d %H:%M")
            })

    scripts_count = len(glob.glob(os.path.join(SCRIPTS_DIR, "*"))) if os.path.exists(SCRIPTS_DIR) else 0

    return {
        "exists": True,
        "path": NOTION_DIR,
        "pages_count": len(md_files),
        "csv_count": len(csv_files),
        "schemas_count": len(sql_files),
        "scripts_count": scripts_count,
        "pages": md_files,
        "csvs": csv_files,
        "schemas": sql_files
    }


def read_notion_file(rel_type: str, filename: str) -> dict:
    """Lit le contenu textuel d'un fichier de sauvegarde Notion."""
    dirs_map = {
        "page": MARKDOWN_DIR,
        "csv": CSV_DIR,
        "schema": SCHEMAS_DIR
    }
    base_d = dirs_map.get(rel_type, MARKDOWN_DIR)
    target = os.path.join(base_d, os.path.basename(filename))
    if not os.path.exists(target):
        return {"success": False, "error": "Fichier introuvable"}
    try:
        with open(target, "r", encoding="utf-8", errors="replace") as f:
            content = f.read(50000)
        return {
            "success": True,
            "filename": os.path.basename(filename),
            "type": rel_type,
            "content": content
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def run_notion_backup_snapshot() -> dict:
    """Exécute un snapshot de sauvegarde consolidé Notion & bases."""
    t0 = time.time()
    os.makedirs(NOTION_DIR, exist_ok=True)
    os.makedirs(CSV_DIR, exist_ok=True)
    os.makedirs(MARKDOWN_DIR, exist_ok=True)
    os.makedirs(SCHEMAS_DIR, exist_ok=True)
    
    actions = []
    
    # 1. Export SQL schema
    try:
        master_db = os.path.expanduser("~/jarvis/jarvis_master.db")
        if os.path.exists(master_db):
            schema_out = os.path.join(SCHEMAS_DIR, "jarvis_master_schema.sql")
            # Python pur (sqlite_master) : plus de dépendance au binaire sqlite3 ni au shell
            n_obj = sqlite_schema_dump(master_db, schema_out)
            actions.append(f"Schéma jarvis_master_schema.sql actualisé ({n_obj} objets)")
    except Exception as e:
        actions.append(f"Erreur export schéma: {e}")

    # 2. Export CSV tables
    try:
        prod_db = os.path.expanduser("~/jarvis/data/production.db")
        if os.path.exists(prod_db):
            csv_out = os.path.join(CSV_DIR, "production_runs.csv")
            # Python pur (module csv, UTF-8) au lieu de « sqlite3 -header -csv … > »
            n_rows = sqlite_export_csv(prod_db, "SELECT * FROM runs", csv_out)
            actions.append(f"Export CSV production_runs.csv créé ({n_rows} lignes)")
    except Exception as e:
        actions.append(f"Erreur export CSV: {e}")

    # 3. Synthèse Markdown
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    summary_file = os.path.join(MARKDOWN_DIR, "JARVIS_OS_NOTION_WORKSPACE.md")
    try:
        with open(summary_file, "w", encoding="utf-8") as f:
            f.write(f"# JARVIS OS — NOTION WORKSPACE SNAPSHOT\n\nDate: {now_str}\n\nSauvegarde des briques unifiées, clusters et bases vivantes.")
        actions.append("JARVIS_OS_NOTION_WORKSPACE.md régénéré")
    except Exception as e:
        actions.append(f"Erreur markdown: {e}")

    elapsed = round(time.time() - t0, 2)
    return {
        "success": True,
        "elapsed": elapsed,
        "actions": actions,
        "summary": f"Sauvegarde Notion exécutée en {elapsed}s ({len(actions)} opérations)"
    }
