# -*- coding: utf-8 -*-
"""
JARVIS COCKPIT — MOTEUR D'ESCOUADE D'AGENTS & SUPERVISION MULTI-SSDs SQL
========================================================================
Gère l'Armée de sous-agents autonomes (Sentinel-GPU, Dev-Pilot, Agent-Scan-SSD...)
et la cartographie multi-disques des 3 SSDs de 1 To avec inspection SQLite.
"""

import os
import time
import json
import sqlite3
import shutil
import urllib.request
from datetime import datetime

MASTER_DB = "/home/turbo/jarvis/jarvis_master.db"

POINTS_SSD = [
    {
        "id": "ssd1",
        "nom": "SSD 1 — Système & Core OS",
        "disque": "/dev/sdb2",
        "point_montage": "/",
        "type": "Système Linux & Jarvis Core",
        "modele": "WD Blue SA510 1TB"
    },
    {
        "id": "ssd2",
        "nom": "SSD 2 — Archives, Backups & M1",
        "disque": "/dev/sda2",
        "point_montage": "/mnt/jarvis-m1",
        "type": "Archives froides & Gros volumes (7GB+)",
        "modele": "WD Blue SA510 1TB"
    },
    {
        "id": "ssd3",
        "nom": "SSD 3 — Mémoires Vivantes, Vectoriel & M6",
        "disque": "/dev/sdc2",
        "point_montage": "/mnt/jarvis-m6",
        "type": "Claude-Mem, Chroma Vectoriel & Données",
        "modele": "WD Blue SA510 1TB"
    }
]


def get_agents_escouade():
    """Récupère la liste de tous les agents de l'escouade."""
    agents = []
    try:
        con = sqlite3.connect(f"file:{MASTER_DB}?mode=ro", uri=True, timeout=3.0)
        c = con.cursor()
        c.execute("""
            SELECT nom, role, mission, modele, statut, nb_exec, derniere_exec, dernier_rapport
            FROM agents_escouade
            ORDER BY nom ASC
        """)
        for row in c.fetchall():
            agents.append({
                "nom": row[0],
                "role": row[1],
                "mission": row[2],
                "modele": row[3],
                "statut": row[4] or "ACTIF",
                "nb_exec": row[5] or 0,
                "derniere_exec": row[6],
                "dernier_rapport": row[7]
            })
        con.close()
    except Exception as e:
        print(f"[ESCOUADE] Erreur lecture agents: {e}")
    return agents


def lancer_agent(nom: str, tache: str, temperature: float = 0.6):
    """Mobilise un sous-agent autonome sur une mission précise."""
    nom_clean = nom.strip()
    try:
        con = sqlite3.connect(MASTER_DB, timeout=5.0)
        c = con.cursor()
        row = c.execute(
            "SELECT nom, role, mission, system_prompt, modele FROM agents_escouade WHERE LOWER(nom) = LOWER(?)",
            (nom_clean,)
        ).fetchone()

        if not row:
            con.close()
            return {"success": False, "error": f"Agent '{nom_clean}' introuvable dans l'escouade."}

        nom_reel, role, mission, sys_prompt, mod = row
        sys_p = sys_prompt or f"Tu es {nom_reel}, sous-agent autonome de JARVIS. Rôle: {role}. Mission: {mission}."

        t0 = time.time()
        texte_rapport = ""

        if mod.startswith("ollama") or (":" in mod and not mod.startswith("qwen")):
            nom_mod_ollama = mod.replace("ollama/", "")
            payload = {
                "model": nom_mod_ollama,
                "prompt": f"[SYSTEM]\n{sys_p}\n[/SYSTEM]\n\n{tache}",
                "stream": False,
                "options": {"temperature": temperature}
            }
            req = urllib.request.Request(
                "http://127.0.0.1:11434/api/generate",
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                texte_rapport = data.get("response", "").strip()
        else:
            payload = {
                "model": mod,
                "messages": [
                    {"role": "system", "content": sys_p},
                    {"role": "user", "content": tache}
                ],
                "temperature": temperature,
                "max_tokens": 800,
                "stream": False
            }
            req = urllib.request.Request(
                "http://127.0.0.1:1234/v1/chat/completions",
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                msg = data["choices"][0]["message"]
                content = msg.get("content") or ""
                reasoning = msg.get("reasoning_content") or ""
                texte_rapport = content.strip() if content.strip() else reasoning.strip()

        elapsed = time.time() - t0

        c.execute("""
            UPDATE agents_escouade
            SET dernier_rapport = ?,
                nb_exec = COALESCE(nb_exec, 0) + 1,
                derniere_exec = datetime('now', 'localtime')
            WHERE nom = ?
        """, (texte_rapport[:3000], nom_reel))
        con.commit()
        con.close()

        return {
            "success": True,
            "nom": nom_reel,
            "role": role,
            "modele": mod,
            "rapport": texte_rapport,
            "elapsed_seconds": round(elapsed, 2),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def get_cartographie_ssd():
    """Télémétrie en direct des 3 disques SSD physiques."""
    resultats = []
    for info in POINTS_SSD:
        pt = info["point_montage"]
        item = dict(info)
        if os.path.exists(pt):
            try:
                stat = shutil.disk_usage(pt)
                total_gb = stat.total / (1024**3)
                used_gb = stat.used / (1024**3)
                free_gb = stat.free / (1024**3)
                pct = round((used_gb / total_gb) * 100, 1)

                item["accessible"] = True
                item["total_gb"] = round(total_gb, 1)
                item["used_gb"] = round(used_gb, 1)
                item["free_gb"] = round(free_gb, 1)
                item["percent_used"] = pct
                item["statut_alerte"] = "CRITIQUE" if pct > 90 else ("VIGILANCE" if pct > 80 else "OPTIMAL")
            except Exception as e:
                item["accessible"] = False
                item["error"] = str(e)
        else:
            item["accessible"] = False
            item["error"] = "Point de montage absent"
        resultats.append(item)
    return resultats


def scanner_bases_sql(filtre="tous"):
    """Scanne les bases SQLite sur les SSDs."""
    racines = []
    f = filtre.strip().lower()
    if f in ("tous", "all"):
        racines = [
            ("SSD 1 (Système)", "/home/turbo/jarvis"),
            ("SSD 2 (Archives)", "/mnt/jarvis-m1"),
            ("SSD 3 (Mémoires)", "/mnt/jarvis-m6"),
        ]
    elif f in ("ssd1", "systeme", "/"):
        racines = [("SSD 1 (Système)", "/home/turbo/jarvis")]
    elif f in ("ssd2", "m1"):
        racines = [("SSD 2 (Archives)", "/mnt/jarvis-m1")]
    elif f in ("ssd3", "m6"):
        racines = [("SSD 3 (Mémoires)", "/mnt/jarvis-m6")]

    bases = []
    for label_ssd, racine in racines:
        if not os.path.exists(racine):
            continue
        count_in_racine = 0
        for dirpath, dirnames, filenames in os.walk(racine):
            if any(skip in dirpath for skip in [".cache", ".local/share/Trash", "node_modules", ".git"]):
                continue
            for fname in filenames:
                if fname.endswith((".db", ".sqlite", ".sqlite3")):
                    p = os.path.join(dirpath, fname)
                    try:
                        sz = os.path.getsize(p)
                        if sz > 2048:
                            sz_mb = sz / (1024 * 1024)
                            sz_str = f"{sz_mb/1024:.2f} Go" if sz_mb > 1024 else f"{sz_mb:.1f} Mo"
                            mtime = datetime.fromtimestamp(os.path.getmtime(p)).strftime("%Y-%m-%d %H:%M")
                            bases.append({
                                "ssd": label_ssd,
                                "nom": fname,
                                "chemin": p,
                                "taille_bytes": sz,
                                "taille_str": sz_str,
                                "modifie_le": mtime
                            })
                            count_in_racine += 1
                    except Exception:
                        pass
            if count_in_racine >= 25:
                break

    bases.sort(key=lambda x: x["taille_bytes"], reverse=True)
    return bases


def inspecter_base_sql(chemin_base: str, limite_tables: int = 15):
    """Inspecte les tables et données d'une base SQLite."""
    if not os.path.exists(chemin_base):
        return {"success": False, "error": f"Fichier '{chemin_base}' introuvable."}

    try:
        con = sqlite3.connect(f"file:{chemin_base}?mode=ro", uri=True, timeout=3.0)
        c = con.cursor()
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
        tables_raw = [r[0] for r in c.fetchall()]

        tables_info = []
        for t in tables_raw[:limite_tables]:
            try:
                c.execute(f'SELECT count(*) FROM "{t}";')
                nb = c.fetchone()[0]
                c.execute(f'PRAGMA table_info("{t}");')
                cols = [col[1] for col in c.fetchall()]
                tables_info.append({"table": t, "count": nb, "columns": cols[:8]})
            except Exception as et:
                tables_info.append({"table": t, "error": str(et)})

        con.close()
        sz = os.path.getsize(chemin_base) / (1024 * 1024)
        sz_str = f"{sz/1024:.2f} Go" if sz > 1024 else f"{sz:.2f} Mo"
        return {
            "success": True,
            "chemin": chemin_base,
            "taille_str": sz_str,
            "total_tables": len(tables_raw),
            "tables": tables_info
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
