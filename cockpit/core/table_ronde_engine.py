#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
table_ronde_engine.py — MOTEUR TABLE RONDE SOUVERAINE & INTÉGRATION BROWSER OS

Connecte les 7 sièges IA du Conseil et les fait délibérer EN PARALLÈLE sur une
question, chacun avec sa persona propre, en s'appuyant sur la cascade
d'inférence locale 0-token (M6 GPU → M4 Ollama → Chat Proxy).

Puis un CONSENSUS réel est synthétisé par un LLM à partir des avis (et non plus
un texte figé), avec un indicateur de confiance basé sur le taux d'avis réels.

Sources de contexte injectées en direct :
  • Board OS  : corpus FTS5 (board.db) via search_board_fts
  • Browser OS: onglets CDP :9222 + historique Chrome récent
  • Agents    : Antigravity (agy :18811) et OpenClaw (:18789) multi-agents

Réécrit le 2026-09-04 :
  - Correctif : injection Board utilisait la clé 'content' (inexistante) au lieu
    de 'snippet' → le contexte Board n'était jamais transmis aux experts.
  - Correctif : le retour ne contenait pas les clés attendues par l'UI PyQt6
    (content / sources_count / source) → l'onglet affichait un cadre vide.
  - Délibération séquentielle → parallèle (ThreadPoolExecutor).
  - Consensus codé en dur → vraie synthèse LLM.
"""

import os
import sys
import json
import time
import shutil
import sqlite3
import tempfile
import subprocess
import urllib.request
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)

from core.config import MASTER_DB, BOARD_DB, M6_HOST, M6_PORT, OLLAMA_URL
from core.database import search_board_fts
from core.inference import generate_completion

# Endpoints réseau du Conseil ------------------------------------------------
REMI_IP = os.environ.get("JARVIS_M1_HOST", "100.112.114.32")  # Nœud M1 (LM Studio)
M1_URL = f"http://{REMI_IP}:1234"
OL_URL = OLLAMA_URL                                            # M4 Ollama local
OPENCLAW_URL = os.environ.get("JARVIS_OPENCLAW_URL", "http://127.0.0.1:18789")
ANTIGRAVITY_URL = os.environ.get("JARVIS_ANTIGRAVITY_URL", "http://127.0.0.1:18811")
CDP_URL = os.environ.get("JARVIS_CDP_URL", "http://127.0.0.1:9222")
BROWSEROS_MCP_URL = "http://127.0.0.1:9003/mcp"

# Badges pour la barre d'experts de l'UI (clé publique conservée) -------------
EXPERTS = [
    {"id": "remi", "name": "🖥️ Rémi (M1)", "color": "#34d399", "role": "Superviseur d'infrastructure et cluster."},
    {"id": "claude", "name": "👑 Claude Code", "color": "#fbbf24", "role": "Architecte logiciel et conception code."},
    {"id": "gemini", "name": "✨ Gemini AI", "color": "#38bdf8", "role": "Synthèse grands volumes & multimodal."},
    {"id": "ollama", "name": "🛡️ Qwen Local", "color": "#22d3ee", "role": "Inférence locale 0-token souveraine."},
    {"id": "openclaw", "name": "🤖 OpenClaw", "color": "#c084fc", "role": "Exécution système OS et orchestration MCP."},
    {"id": "chatgpt", "name": "💬 ChatGPT", "color": "#2dd4bf", "role": "Alignement stratégique & vision produit."},
    {"id": "mistral", "name": "⚡ Mistral AI", "color": "#fb923c", "role": "Optimisation latence et calculs GPU."}
]

# Définition détaillée des 7 sièges (persona + routage modèle préféré) --------
# preferred : indice pour le routage d'inférence.
#   "m1"      -> tente d'abord le nœud M1 (LM Studio) puis cascade
#   "ollama:<modele>" -> force un modèle Ollama précis puis cascade
#   None      -> cascade standard M6 → M4 → proxy
SIEGES = [
    {
        "id": "remi", "nom": "Rémi (Nœud Stratégique M1)",
        "role": "Superviseur d'infrastructure et garant de la continuité opérationnelle du cluster distribué.",
        "avatar": "fa-server text-emerald-400", "badge": f"M1 · {REMI_IP}", "preferred": "m1",
    },
    {
        "id": "claude", "nom": "Claude Code (Architecte Code & Logique)",
        "role": "Architecte logiciel, vérificateur de syntaxe, rigueur formelle et conception de code propre.",
        "avatar": "fa-crown text-amber-400", "badge": "Anthropic CLI", "preferred": None,
    },
    {
        "id": "gemini", "nom": "Gemini AI Studio (Synthèse & Multimodal)",
        "role": "Analyse rapide de grands volumes de données, créativité et projection écosystème.",
        "avatar": "fa-wand-magic-sparkles text-sky-400", "badge": "Google AI Studio", "preferred": None,
    },
    {
        "id": "ollama", "nom": "Qwen 2.5 Local (Souveraineté 0-Token)",
        "role": "Calcul d'inférence déconnecté, sécurité totale sans fuite de données hors de la machine.",
        "avatar": "fa-shield-halved text-cyan-400", "badge": "Local :11434", "preferred": "ollama:qwen2.5:7b",
    },
    {
        "id": "openclaw", "nom": "Manus / OpenClaw (Agent Exécutant & PWA)",
        "role": "Exécution d'actions sur le système d'exploitation, orchestration des outils MCP et navigation.",
        "avatar": "fa-robot text-purple-400", "badge": "Gateway :18789", "preferred": None,
    },
    {
        "id": "chatgpt", "nom": "ChatGPT (Gouvernance & Stratégie Produit)",
        "role": "Alignement stratégique, modélisation des besoins utilisateurs et vision globale.",
        "avatar": "fa-comments text-teal-400", "badge": "Browser OS Hub", "preferred": None,
    },
    {
        "id": "mistral", "nom": "Mistral AI (Spécialiste Algorithmique)",
        "role": "Optimisation des performances brutes, latences GPU et logique européenne souveraine.",
        "avatar": "fa-wind text-orange-400", "badge": "Inférence Rapide", "preferred": "ollama:mistral",
    },
]

# Repli heuristique par siège si TOUS les moteurs sont indisponibles ----------
FALLBACK_OPINIONS = {
    "remi": "Pour l'infrastructure M1/M4, la résilience repose sur le partitionnement des données et le maintien de la synchronisation continue du cluster.",
    "claude": "Du point de vue du code, je préconise une approche modulaire découplée avec typage strict et gestion des erreurs par couches.",
    "gemini": "L'intégration multimodale et l'exploitation des traces vivantes permettent une vision globale et réactive.",
    "ollama": "L'inférence locale garantit une confidentialité absolue et une faible latence sans dépendance externe.",
    "openclaw": "Je peux exécuter directement les commandes via le protocole MCP et synchroniser l'état du bureau.",
    "chatgpt": "La clé stratégique est de préserver une cohérence fonctionnelle complète entre interfaces et besoins prioritaires.",
    "mistral": "L'efficacité énergétique et la vitesse de traitement restent optimales en mutualisant le contexte partagé.",
}


# ── Contexte Browser OS ─────────────────────────────────────────────────────
def get_browser_os_context() -> dict:
    """Récupère le contexte temps réel de Browser OS (onglets CDP, historique récent)."""
    ctx = {
        "disponible": False,
        "active_tabs": [],
        "recent_history": [],
        "cookies_summary": "Profils Chrome (ChatGPT, Claude, Gemini, Mistral)",
        "source": "Chrome CDP & Profils Locaux",
    }

    # 1. Onglets ouverts via Chrome CDP :9222
    try:
        req = urllib.request.Request(f"{CDP_URL}/json/list")
        with urllib.request.urlopen(req, timeout=1.0) as resp:
            tabs = json.loads(resp.read().decode())
            ctx["active_tabs"] = [
                {"title": t.get("title", "Sans titre")[:80], "url": t.get("url", "")[:100]}
                for t in tabs if t.get("type") == "page"
            ][:6]
            ctx["disponible"] = True
    except Exception:
        ctx["active_tabs"] = []

    # 2. Historique Chrome récent (copie temporaire propre, nettoyée ensuite)
    history_db = os.path.expanduser("~/.config/google-chrome/Default/History")
    if os.path.exists(history_db):
        tmp_hist = None
        try:
            fd, tmp_hist = tempfile.mkstemp(prefix="jarvis_chrome_hist_", suffix=".db")
            os.close(fd)
            shutil.copyfile(history_db, tmp_hist)
            conn = sqlite3.connect(f"file:{tmp_hist}?mode=ro", uri=True, timeout=1.5)
            c = conn.cursor()
            c.execute("SELECT title, url FROM urls ORDER BY last_visit_time DESC LIMIT 5")
            ctx["recent_history"] = [{"title": (r[0] or "")[:70], "url": (r[1] or "")[:90]} for r in c.fetchall()]
            conn.close()
            ctx["disponible"] = True
        except Exception:
            pass
        finally:
            if tmp_hist and os.path.exists(tmp_hist):
                try:
                    os.remove(tmp_hist)
                except OSError:
                    pass

    return ctx


# ── État de connectivité des agents ─────────────────────────────────────────
def _http_ok(url: str, timeout: float = 0.8) -> bool:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Jarvis-Cockpit"})
        with urllib.request.urlopen(req, timeout=timeout):
            return True
    except Exception:
        return False


def check_agent_status() -> dict:
    """Vérifie l'état de connectivité de chacun des sièges + agents multi (agy/OpenClaw)."""
    status = {}

    # 1. Ollama Qwen (M4 local)
    try:
        req = urllib.request.Request(f"{OL_URL}/api/tags")
        with urllib.request.urlopen(req, timeout=0.8) as resp:
            data = json.loads(resp.read().decode())
            models = [m.get("name") for m in data.get("models", [])]
            status["ollama"] = {"en_ligne": True, "detail": models[0] if models else "Qwen2.5"}
    except Exception:
        status["ollama"] = {"en_ligne": False, "detail": "Service local inactif"}

    # 2. Rémi (Tailscale M1)
    try:
        r = subprocess.run(["ping", "-c", "1", "-W", "1", REMI_IP], capture_output=True, timeout=1.2)
        status["remi"] = {"en_ligne": (r.returncode == 0), "ip": REMI_IP, "detail": "Nœud M1 RJ45/Tailscale"}
    except Exception:
        status["remi"] = {"en_ligne": False, "ip": REMI_IP, "detail": "Hors portée réseau"}

    # 3. Claude Code CLI
    claude_bin = os.path.expanduser("~/.local/bin/claude")
    status["claude"] = {"en_ligne": os.path.exists(claude_bin), "detail": "CLI local"}

    # 4. OpenClaw / Manus (moteur multi-agents ACP)
    status["openclaw"] = {
        "en_ligne": _http_ok(f"{OPENCLAW_URL}/health"),
        "detail": "Passerelle multi-agents :18789",
    }

    # 5. Antigravity (agy — pont IDE multi-agents Google)
    status["antigravity"] = {
        "en_ligne": _http_ok(ANTIGRAVITY_URL, timeout=0.6),
        "detail": "Pont agents Antigravity :18811",
    }

    # 6. Gemini AI Studio (présence profil)
    gemini_dir = os.path.expanduser("~/.gemini")
    status["gemini"] = {"en_ligne": os.path.exists(gemini_dir), "detail": "Profils & Antigravity connectés"}

    # 7. ChatGPT / Browser OS
    status["browser_os"] = {"en_ligne": _http_ok(f"{CDP_URL}/json/version"), "detail": "CDP 9222 & profils Chrome"}

    # 8. Mistral (via moteurs locaux)
    status["mistral"] = {"en_ligne": status["ollama"]["en_ligne"], "detail": "Moteur souverain M6/Ollama"}

    return status


# ── Inférence d'un siège (routage préféré + cascade) ────────────────────────
def _infer_m1(prompt: str, sys_prompt: str, timeout: float = 12.0) -> dict:
    """Tente une inférence sur le nœud M1 (LM Studio, API OpenAI-compatible)."""
    try:
        payload = json.dumps({
            "model": "local-model",
            "messages": [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.5,
            "max_tokens": 320,
        }).encode("utf-8")
        req = urllib.request.Request(f"{M1_URL}/v1/chat/completions", data=payload,
                                     headers={"Content-Type": "application/json"})
        t0 = time.time()
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
            msg = data["choices"][0]["message"]
            content = (msg.get("content") or msg.get("reasoning_content") or "").strip()
            if content:
                return {"content": content, "source": f"M1 LM Studio ({REMI_IP})", "success": True,
                        "latency": round(time.time() - t0, 2)}
    except Exception:
        pass
    return {"success": False}


def _infer_ollama(prompt: str, sys_prompt: str, model: str, timeout: float = 18.0) -> dict:
    """Tente une inférence Ollama sur un modèle précis."""
    try:
        payload = json.dumps({
            "model": model,
            "prompt": sys_prompt + "\n\n" + prompt,
            "stream": False,
            "options": {"temperature": 0.5, "num_predict": 320},
        }).encode("utf-8")
        req = urllib.request.Request(f"{OL_URL}/api/generate", data=payload,
                                     headers={"Content-Type": "application/json"})
        t0 = time.time()
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
            content = (data.get("response") or "").strip()
            if content:
                return {"content": content, "source": f"M4 Ollama ({model})", "success": True,
                        "latency": round(time.time() - t0, 2)}
    except Exception:
        pass
    return {"success": False}


def _deliberer_siege(siege: dict, question: str, ctx_str: str) -> dict:
    """Produit l'avis d'un siège, avec routage préféré puis cascade puis repli."""
    t_start = time.time()
    sys_prompt = (
        f"Tu es {siege['nom']}. Rôle : {siege['role']} "
        "Tu sièges à la Table Ronde souveraine de JARVIS. Réponds en 2 à 4 phrases "
        "concrètes, précises et directes, strictement dans ton domaine d'excellence. "
        "Pas de politesses, pas de préambule."
    )
    prompt = f"Question soumise au Conseil :\n« {question} »"
    if ctx_str:
        prompt += f"\n\nContexte vérifié à exploiter :\n{ctx_str}"

    preferred = siege.get("preferred")
    result = {"success": False}

    # 1. Routage préféré
    if preferred == "m1":
        result = _infer_m1(prompt, sys_prompt)
    elif preferred and preferred.startswith("ollama:"):
        result = _infer_ollama(prompt, sys_prompt, preferred.split(":", 1)[1])

    # 2. Cascade générique (M6 → M4 → proxy) — budget court : 2-4 phrases
    if not result.get("success"):
        result = generate_completion(prompt, sys_prompt=sys_prompt, max_tokens=160, temperature=0.5)

    # 3. Repli heuristique hors-ligne
    if result.get("success"):
        opinion = result["content"].strip()
        source = result.get("source", "Inférence locale")
        reel = True
    else:
        opinion = FALLBACK_OPINIONS.get(siege["id"], f"Avis aligné sur : {question}")
        source = "Conseil Souverain (heuristique hors-ligne)"
        reel = False

    return {
        "id": siege["id"],
        "expert": siege["nom"],
        "role": siege["role"],
        "avatar": siege["avatar"],
        "badge": siege["badge"],
        "opinion": opinion,
        "source": source,
        "reel": reel,
        "latency": round(time.time() - t_start, 2),
    }


def _synthetiser_consensus(question: str, deliberations: list, ctx_str: str) -> dict:
    """Synthétise un vrai consensus à partir des avis, via LLM (avec repli)."""
    avis = "\n".join([f"- {d['expert']} : {d['opinion']}" for d in deliberations])
    sys_prompt = (
        "Tu es le Président de la Table Ronde souveraine de JARVIS. À partir des avis "
        "des experts, tu produis une SYNTHÈSE d'arbitrage rigoureuse."
    )
    prompt = (
        f"Question : « {question} »\n\n"
        f"Avis des experts :\n{avis}\n\n"
        "Rédige la synthèse en trois parties courtes et balisées ainsi :\n"
        "CONVERGENCES : les points d'accord.\n"
        "TENSIONS : les divergences ou risques.\n"
        "DÉCISION : la recommandation opérationnelle concrète (2-3 actions numérotées).\n"
        "Sois factuel et actionnable, pas de remplissage."
    )
    res = generate_completion(prompt, sys_prompt=sys_prompt, max_tokens=320, temperature=0.35)
    if res.get("success") and res.get("content", "").strip():
        return {"texte": res["content"].strip(), "source": res.get("source", "Synthèse LLM"), "reel": True}

    # Repli déterministe (jamais de faux « unanimité » : on résume les avis réels)
    resume = " ".join([d["opinion"].split(".")[0].strip() + "." for d in deliberations[:3] if d["opinion"]])
    texte = (
        f"CONVERGENCES : {resume}\n"
        "TENSIONS : moteurs LLM indisponibles — synthèse dégradée à partir des avis bruts.\n"
        f"DÉCISION : 1) Traiter « {question} » selon les avis ci-dessus ; "
        "2) relancer la délibération une fois un moteur d'inférence en ligne."
    )
    return {"texte": texte, "source": "Synthèse dégradée (hors-ligne)", "reel": False}


# ── Formatage du rendu texte pour l'UI PyQt6 ────────────────────────────────
def _formater_content(question: str, deliberations: list, consensus: dict,
                      confiance: int, total_latency: float) -> str:
    lignes = []
    lignes.append("═" * 68)
    lignes.append(f"  TABLE RONDE — « {question} »")
    lignes.append(f"  {len(deliberations)} experts · {confiance}% d'avis réels (LLM) · {total_latency}s")
    lignes.append("═" * 68)
    lignes.append("")
    for i, d in enumerate(deliberations, 1):
        marque = "🟢" if d["reel"] else "⚪"
        lignes.append(f"{marque} {i}. {d['expert']}   [{d['source']} · {d['latency']}s]")
        lignes.append(f"    {d['opinion']}")
        lignes.append("")
    lignes.append("─" * 68)
    lignes.append(f"⚖️  CONSENSUS DU CONSEIL   [{consensus['source']}]")
    lignes.append("─" * 68)
    lignes.append(consensus["texte"])
    return "\n".join(lignes)


# ── Persistance de la trace ─────────────────────────────────────────────────
def _persister_trace(question: str, ctx_str: str, deliberations: list, consensus_txt: str) -> None:
    try:
        conn = sqlite3.connect(MASTER_DB, timeout=4.0)
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS traces_table_ronde (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date_heure TEXT, question TEXT, contexte TEXT,
                deliberation_json TEXT, consensus TEXT
            )
        """)
        c.execute("""
            INSERT INTO traces_table_ronde (date_heure, question, contexte, deliberation_json, consensus)
            VALUES (?, ?, ?, ?, ?)
        """, (datetime.now().isoformat(), question, ctx_str[:1000],
              json.dumps(deliberations, ensure_ascii=False), consensus_txt))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[TABLE RONDE] Erreur sauvegarde trace: {e}")


# ── Point d'entrée principal ────────────────────────────────────────────────
def run_table_ronde_deliberation(question: str, injecter_browser: bool = True,
                                 injecter_board: bool = True,
                                 agents_selectionnes: list = None) -> dict:
    """Exécute une délibération complète de la Table Ronde (parallèle + consensus LLM)."""
    t0 = time.time()
    question = (question or "").strip()
    if not question:
        return {
            "success": False, "question": question, "content": "Aucune question fournie.",
            "sources_count": 0, "source": "N/A", "deliberation": [], "consensus": "",
        }

    # 1. Contexte enrichi -----------------------------------------------------
    extra_context = []
    sources_count = 0

    if injecter_board:
        try:
            chunks = search_board_fts(question, limit=3)
            sources_count = len(chunks)
            if chunks:
                extra_context.append(
                    "=== CONNAISSANCES BOARD OS (corpus FTS5) ===\n" +
                    "\n".join([f"• [{c.get('title', 'doc')}] : {c.get('snippet', '')}" for c in chunks])
                )
        except Exception:
            pass

    if injecter_browser:
        b_ctx = get_browser_os_context()
        b_summary = []
        if b_ctx.get("active_tabs"):
            b_summary.append("Onglets actifs : " + ", ".join([t["title"] for t in b_ctx["active_tabs"][:3]]))
        if b_ctx.get("recent_history"):
            b_summary.append("Historique récent : " + ", ".join([h["title"] for h in b_ctx["recent_history"][:3]]))
        if b_summary:
            extra_context.append("=== CONTEXTE BROWSER OS (Navigation) ===\n" + "\n".join(b_summary))

    ctx_str = "\n\n".join(extra_context)

    # 2. Sélection des sièges -------------------------------------------------
    sieges = SIEGES
    if agents_selectionnes:
        sieges = [s for s in SIEGES if s["id"] in agents_selectionnes] or SIEGES

    # 3. Délibération EN PARALLÈLE --------------------------------------------
    deliberations = [None] * len(sieges)
    with ThreadPoolExecutor(max_workers=min(7, len(sieges))) as pool:
        futures = {pool.submit(_deliberer_siege, s, question, ctx_str): i for i, s in enumerate(sieges)}
        for fut in as_completed(futures):
            idx = futures[fut]
            try:
                deliberations[idx] = fut.result()
            except Exception as e:
                s = sieges[idx]
                deliberations[idx] = {
                    "id": s["id"], "expert": s["nom"], "role": s["role"],
                    "avatar": s["avatar"], "badge": s["badge"],
                    "opinion": FALLBACK_OPINIONS.get(s["id"], "Avis indisponible."),
                    "source": f"Erreur ({e})", "reel": False, "latency": 0.0,
                }
    deliberations = [d for d in deliberations if d]

    # 4. Consensus réel -------------------------------------------------------
    consensus = _synthetiser_consensus(question, deliberations, ctx_str)

    # 5. Indicateur de confiance (part d'avis réellement produits par LLM) ----
    nb_reels = sum(1 for d in deliberations if d.get("reel"))
    confiance = round(100 * nb_reels / len(deliberations)) if deliberations else 0

    total_time = round(time.time() - t0, 2)
    content = _formater_content(question, deliberations, consensus, confiance, total_time)

    # 6. Persistance ----------------------------------------------------------
    _persister_trace(question, ctx_str, deliberations, consensus["texte"])

    # 7. Retour (clés GUI + clés web/structurées) -----------------------------
    return {
        "success": True,
        "question": question,
        "content": content,                       # ← attendu par l'onglet PyQt6
        "sources_count": sources_count,           # ← attendu par l'onglet PyQt6
        "source": f"Table Ronde · {confiance}% réel · {consensus['source']}",
        "confidence": confiance,
        "total_latency": total_time,
        "browser_context_included": injecter_browser,
        "board_context_included": injecter_board,
        "deliberation": deliberations,            # ← structuré (web / traces)
        "consensus": consensus["texte"],
    }


# ── Test manuel en ligne de commande ────────────────────────────────────────
if __name__ == "__main__":
    q = " ".join(sys.argv[1:]) or "Comment fiabiliser la synchronisation du cluster M4/M1 ?"
    out = run_table_ronde_deliberation(q)
    print(out["content"])
    print(f"\n[meta] success={out['success']} confiance={out['confidence']}% "
          f"sources_board={out['sources_count']} latence={out['total_latency']}s")
