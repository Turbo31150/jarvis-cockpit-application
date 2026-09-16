#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JARVIS CORE LOOP — boucle executor runtime (anti-simulation).

Le correctif RÉEL au problème « Qwen raconte au lieu d'exécuter » : ce n'est pas
un system prompt, c'est CE runtime. Il expose de VRAIS outils à Qwen2.5-7B via
l'API function-calling de LM Studio, EXÉCUTE réellement les tool_calls, réinjecte
les résultats, détecte le WRONG_MODE (narration sans tool_call) et relance en
contrainte stricte, puis envoie la réponse finale au moteur TTS (Kokoro ff_siwis).

Pipeline : TEXTE(STT) → QWEN(tools) → TOOL réel → RESULT → QWEN → … → VERIFY →
           FINAL → TTS → VOIX

Usage :
    python jarvis_core_loop.py "Vérifie que le moteur vocal tourne et dis-le."
    python jarvis_core_loop.py --no-speak "..."   # sans TTS
"""
from __future__ import annotations
import os
import re
import sys
import json
import subprocess
import urllib.request

LMSTUDIO = "http://127.0.0.1:1234/v1/chat/completions"
MODEL = os.environ.get("JARVIS_CORE_MODEL", "qwen2.5-7b")
# Pass VERIFY : 2e cerveau qui relit la phrase finale (tool_use, ctx ~14k). qwen3-8b
# est meilleur en cohérence/langue que qwen2.5-7b et corrige ses quirks (oubli --user,
# artefact chinois de fin). Chargé sur la MÊME instance LM Studio (:1234).
VERIFY_MODEL = os.environ.get("JARVIS_VERIFY_MODEL", "qwen3-8b")
VERIFY_ENABLED = os.environ.get("JARVIS_VERIFY", "1") != "0"
CORE_PROMPT = os.path.expanduser("~/prompts/JARVIS_CORE_VOCAL.md")
TTS_WRAPPER = os.path.expanduser("~/jarvis/bin/jarvis-tts-souverain.sh")
DISPATCHER = os.path.expanduser("~/jarvis/bin/jarvis-dispatch-tmux.sh")  # dispatch tmux cockpit

MAX_TOOL_LOOPS = 8
NARRATION = ("je vais", "nous allons", "voici comment", "simulons", "il faudrait",
             "je pourrais", "voulez-vous que", "je vais maintenant")
# garde-fou : commandes destructrices bloquées (ActionPolicy : DELETE/IRREVERSIBLE protégés)
BASH_DENY = ("rm -rf /", "mkfs", "dd if=", ":(){", "shutdown", "reboot", "> /dev/sd")


# ------------------------------------------------------------------ outils réels
def tool_run_bash(cmd: str, background: bool = False) -> str:
    """Exécute une commande bash. background=True → la dispatche dans le cockpit
    (tmux jc-dispatch:bash) : exécution immédiate, NON bloquante pour la boucle
    (idéal commandes longues : build, watch, serveur). Lire la sortie ensuite
    avec l'outil tmux_capture."""
    low = cmd.lower()
    if any(d in low for d in BASH_DENY):
        return "REFUSÉ (commande destructrice bloquée par ActionPolicy)"
    if background:
        try:
            subprocess.run([DISPATCHER, "bash", cmd], capture_output=True,
                           text=True, timeout=15)
            return ("dispatché en arrière-plan dans le cockpit (tmux jc-dispatch:bash), "
                    "exécution immédiate et NON bloquante. Appelle l'outil tmux_capture "
                    "(window=bash) après un court délai pour lire la sortie réelle.")
        except Exception as e:
            return f"ERREUR dispatch tmux: {e}"
    try:
        r = subprocess.run(["bash", "-lc", cmd], capture_output=True, text=True,
                           timeout=60)
        out = (r.stdout or "") + (("\n[stderr] " + r.stderr) if r.stderr else "")
        return f"rc={r.returncode}\n{out.strip()[:2000]}"
    except subprocess.TimeoutExpired:
        return ("TIMEOUT 60s : commande trop longue pour le mode bloquant. "
                "Relance-la avec background=true (elle tournera dans le cockpit tmux), "
                "puis lis la sortie avec tmux_capture.")
    except Exception as e:
        return f"ERREUR: {e}"


def tool_tmux_capture(window: str = "bash") -> str:
    """Lit la sortie réelle d'un pane du cockpit (tmux jc-dispatch:<window>)."""
    if window not in ("bash", "python3"):
        window = "bash"
    try:
        r = subprocess.run([DISPATCHER, "capture", window], capture_output=True,
                           text=True, timeout=15)
        return (r.stdout or "").strip()[:2000] or "(pane vide)"
    except Exception as e:
        return f"ERREUR: {e}"


def tool_read_file(path: str) -> str:
    try:
        with open(os.path.expanduser(path), encoding="utf-8", errors="replace") as f:
            return f.read()[:2000]
    except Exception as e:
        return f"ERREUR: {e}"


def tool_speak(text: str) -> str:
    out = f"/tmp/jarvis-core-speak-{os.getpid()}.wav"
    try:
        r = subprocess.run([TTS_WRAPPER, text, out], capture_output=True, timeout=60)
        ok = r.returncode == 0 and os.path.exists(out) and os.path.getsize(out) > 0
        return f"audio={'OK' if ok else 'ÉCHEC'} path={out}"
    except Exception as e:
        return f"ERREUR: {e}"


# --- outils Turbo OS : écrire du code / lister / consulter (RAG + SQL) ---
BOARD_DB = os.path.expanduser("~/jarvis/board/board.db")
RAG_BIN = os.path.expanduser("~/jarvis/bin/jarvis-rag")
# écriture refusée dans les arborescences système (ActionPolicy)
_WRITE_BLOCKED = ("/etc", "/usr", "/bin", "/sbin", "/boot", "/sys", "/proc",
                  "/root", "/lib", "/lib64", "/var/lib")


def tool_write_file(path: str, content: str) -> str:
    """Écrit un fichier texte (crée les dossiers parents, backup .bak si écrasement).
    Pour écrire du code, des configs, des notes. Refuse les chemins système."""
    p = os.path.abspath(os.path.expanduser(path))
    if p.startswith(_WRITE_BLOCKED) or "/.ssh" in p:
        return "REFUSÉ (écriture dans un chemin système protégé, ActionPolicy)"
    try:
        os.makedirs(os.path.dirname(p) or ".", exist_ok=True)
        backed = False
        if os.path.exists(p):
            try:
                import shutil
                shutil.copy2(p, p + ".bak")
                backed = True
            except Exception:
                pass
        with open(p, "w", encoding="utf-8") as f:
            f.write(content)
        return f"écrit OK : {p} ({len(content)} caractères)" + (" [backup .bak]" if backed else "")
    except Exception as e:
        return f"ERREUR: {e}"


def tool_list_dir(path: str = ".") -> str:
    """Liste le contenu d'un dossier (fichiers + tailles, dossiers avec /)."""
    p = os.path.abspath(os.path.expanduser(path))
    try:
        out = []
        for name in sorted(os.listdir(p))[:200]:
            fp = os.path.join(p, name)
            out.append(f"{name}/" if os.path.isdir(fp) else f"{name} ({os.path.getsize(fp)}o)")
        return f"{p} :\n" + "\n".join(out) if out else f"{p} : (vide)"
    except Exception as e:
        return f"ERREUR: {e}"


def tool_rag_search(query: str) -> str:
    """Consulte la bibliothèque vivante (board.db, ~1,1M passages) via le RAG local.
    Renvoie les extraits pertinents sourcés."""
    try:
        r = subprocess.run([RAG_BIN, "search", query], capture_output=True,
                           text=True, timeout=45)
        out = (r.stdout or "").strip() or (r.stderr or "").strip()
        return out[:2000] or "(aucun résultat)"
    except Exception as e:
        return f"ERREUR: {e}"


def tool_sql_query(query: str) -> str:
    """Interroge board.db en LECTURE SEULE (SELECT/WITH/PRAGMA). Consulter des données
    (compteurs, experts, claims, sources). Les écritures sont refusées."""
    q = query.strip().rstrip(";")
    if not re.match(r"(?is)^\s*(select|with|pragma)\b", q):
        return "REFUSÉ (lecture seule : seules SELECT/WITH/PRAGMA sont permises)"
    if re.search(r"(?is)\b(insert|update|delete|drop|alter|create|attach|replace)\b", q):
        return "REFUSÉ (mot-clé d'écriture détecté ; board.db est en lecture seule ici)"
    try:
        import sqlite3
        con = sqlite3.connect(f"file:{BOARD_DB}?mode=ro", uri=True, timeout=8)
        con.row_factory = sqlite3.Row
        rows = con.execute(q).fetchmany(50)
        con.close()
        if not rows:
            return "(0 ligne)"
        cols = list(rows[0].keys())
        lines = [" | ".join(cols)]
        for row in rows:
            lines.append(" | ".join(str(row[c])[:60] for c in cols))
        return "\n".join(lines)
    except Exception as e:
        return f"ERREUR: {e}"


PC_CONTROL = os.path.expanduser("~/jarvis/voice_pipeline/pc_control.py")
def tool_pc_control(action: str, arg: str = "") -> str:
    """Pilote le PC (X11 :1) : voir l'écran, lister fenêtres, ouvrir/focus apps, filmer.
    Les actions destructrices (click/type) ne sont PAS exposées en auto (sécurité)."""
    allowed = {"screenshot", "list_windows", "active_window", "open_app",
               "focus_window", "video_record", "geometry"}
    if action not in allowed:
        return f"action inconnue ({action}). Choix : {', '.join(sorted(allowed))}"
    args = ["python3", PC_CONTROL, action] + ([arg] if arg else [])
    try:
        r = subprocess.run(args, capture_output=True, text=True, timeout=40,
                           env={**os.environ, "DISPLAY": ":1",
                                "XAUTHORITY": "/run/user/1000/gdm/Xauthority"})
        return (r.stdout or r.stderr).strip()[:1500]
    except Exception as e:
        return f"ERREUR: {e}"


TOOLS = {
    "run_bash": tool_run_bash,
    "read_file": tool_read_file,
    "pc_control": tool_pc_control,
    "write_file": tool_write_file,
    "list_dir": tool_list_dir,
    "rag_search": tool_rag_search,
    "sql_query": tool_sql_query,
    "speak": tool_speak,
    "tmux_capture": tool_tmux_capture,
}

TOOL_SPECS = [
    {"type": "function", "function": {
        "name": "run_bash",
        "description": "Exécute une commande bash (renvoie rc+stdout+stderr). "
                       "Commande longue/bloquante : background=true (part en tmux), puis tmux_capture.",
        "parameters": {"type": "object", "properties": {
            "cmd": {"type": "string"},
            "background": {"type": "boolean", "description": "true = dispatch tmux non bloquant (commande longue)"}},
            "required": ["cmd"]}}},
    {"type": "function", "function": {
        "name": "read_file", "description": "Lit un fichier texte et renvoie son contenu (tronqué).",
        "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}},
    {"type": "function", "function": {
        "name": "speak", "description": "Vocalise un texte via le moteur TTS souverain (Kokoro ff_siwis).",
        "parameters": {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}}},
    {"type": "function", "function": {
        "name": "tmux_capture",
        "description": "Lit la sortie réelle d'une commande dispatchée en arrière-plan dans le cockpit "
                       "(tmux jc-dispatch). window = bash ou python3.",
        "parameters": {"type": "object", "properties": {
            "window": {"type": "string", "enum": ["bash", "python3"]}}, "required": []}}},
    {"type": "function", "function": {
        "name": "write_file",
        "description": "Écrit/crée un fichier (code, config, note). Crée les dossiers parents, "
                       "fait un backup .bak si le fichier existe. Refuse les chemins système.",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string"}, "content": {"type": "string"}},
            "required": ["path", "content"]}}},
    {"type": "function", "function": {
        "name": "list_dir", "description": "Liste le contenu d'un dossier (fichiers, tailles, sous-dossiers).",
        "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": []}}},
    {"type": "function", "function": {
        "name": "rag_search",
        "description": "Consulte la bibliothèque vivante (board.db, ~1,1M passages, 64 experts) via le RAG "
                       "local et renvoie des extraits sourcés. Pour répondre avec la connaissance du système.",
        "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}},
    {"type": "function", "function": {
        "name": "sql_query",
        "description": "Interroge board.db en LECTURE SEULE (SELECT/WITH/PRAGMA) pour consulter des données "
                       "(compteurs, experts, claims, sources). Les écritures sont refusées.",
        "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}},
    {"type": "function", "function": {
        "name": "pc_control",
        "description": "Pilote le PC (écran/fenêtres/apps). action=screenshot (voir l'écran), list_windows "
                       "(fenêtres ouvertes), active_window, open_app (arg=nom), focus_window (arg=titre), "
                       "video_record (arg=secondes).",
        "parameters": {"type": "object", "properties": {
            "action": {"type": "string", "enum": ["screenshot", "list_windows", "active_window",
                                                  "open_app", "focus_window", "video_record"]},
            "arg": {"type": "string"}}, "required": ["action"]}}},
]


def _post(payload: dict) -> dict:
    req = urllib.request.Request(
        LMSTUDIO, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read().decode())


# Prompt court et exécutif pour la boucle outils (le V5 complet reste le cœur
# conversationnel ; ici on veut du tool-calling franc, pas de la doctrine).
# Prompt COURT et exécutif : la combinaison « 4 tool specs complets + prompt long »
# faisait dérailler qwen2.5-7b en tool-calls in-band malformés (diagnostiqué). Court =
# tool_calls structurés propres. On garde seulement les règles indispensables.
LOOP_SYSTEM = (
    "Tu es TURBO OS, MODE EXECUTION (assistant IA local souverain). Outils réels : run_bash, "
    "read_file, write_file, list_dir, rag_search, sql_query, pc_control, speak, tmux_capture. Pour agir, "
    "APPELLE l'outil — ne narre pas, ne simule pas. Écrire du code/fichier → write_file. "
    "Voir l'écran / lister fenêtres / ouvrir une app / filmer → pc_control. "
    "Question de CONNAISSANCE (sens, doctrine) → rag_search. Question de COMPTAGE/CHIFFRE "
    "(combien de domaines/experts/claims/sources/chunks) → sql_query, ex : "
    "SELECT count(*) FROM experts (tables: domains, experts, claims, sources, chunks). "
    "Les services système sont des services UTILISATEUR : toujours « systemctl --user … ». "
    "Commande longue/bloquante : run_bash background=true, puis tmux_capture. "
    "Terminé : UNE phrase française naturelle (ni JSON, ni chemin, ni détail technique). "
    "Ne te présente JAMAIS comme « JARVIS » — ton identité est Turbo OS."
)


def _system_prompt() -> str:
    return LOOP_SYSTEM


def _find_json_objects(s: str):
    """Extrait tous les objets JSON de premier niveau (matching d'accolades, en
    ignorant les accolades à l'intérieur des chaînes). Robuste à l'imbrication —
    contrairement à une regex `[^{}]*` qui casse dès qu'il y a un objet imbriqué."""
    objs, depth, start, in_str, esc = [], 0, None, False, False
    for i, ch in enumerate(s):
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            if depth > 0:
                depth -= 1
                if depth == 0 and start is not None:
                    objs.append(s[start:i + 1])
                    start = None
    return objs


def _lenient_loads(blob: str):
    """json.loads tolérant. qwen ajoute parfois des backslashs invalides à la mode
    shell (ex. \\' — illégal en JSON). Réparation FIDÈLE : on double les backslashs
    non suivis d'un échappement JSON valide, ce qui rend le JSON parsable SANS
    altérer le contenu de la commande (pas de corruption du quoting bash)."""
    try:
        return json.loads(blob)
    except Exception:
        pass
    repaired = re.sub(r'\\(?!["\\/bfnrtu])', r'\\\\', blob)
    try:
        return json.loads(repaired)
    except Exception:
        return None


def _extract_inband_calls(content: str):
    """Fallback : Qwen émet parfois le tool call en TEXTE au lieu du champ structuré,
    et souvent MALFORMÉ (préfixe parasite, balise <tool_call> ouvrante manquante,
    JSON à accolades imbriquées). On retire les balises orphelines, on scanne tous
    les objets JSON de premier niveau et on retient ceux dont `name` est un vrai outil."""
    calls = []
    cleaned = re.sub(r"</?tool_call>", " ", content)
    for blob in _find_json_objects(cleaned):
        o = _lenient_loads(blob)
        if not isinstance(o, dict):
            continue
        name = o.get("name")
        if name not in TOOLS:
            continue
        args = o.get("arguments")
        if args is None:
            args = o.get("parameters") or {}
        if isinstance(args, str):                     # arguments parfois re-sérialisés
            args = _lenient_loads(args) or {}
        if not isinstance(args, dict):
            args = {}
        calls.append((name, args))
    return calls


def _looks_like_tool_blob(content: str) -> bool:
    """Vrai si le « contenu final » ressemble en réalité à un appel d'outil (mal
    formé, jamais exécuté) plutôt qu'à une phrase — pour empêcher VERIFY d'inventer
    un fait à partir d'un blob non exécuté."""
    if "<tool_call>" in content or "</tool_call>" in content:
        return True
    return bool(_extract_inband_calls(content))


# ---------------------------------------------------------------- pass VERIFY
# Prompt de contrôle qualité : qwen3-8b relit la phrase finale de l'exécuteur à la
# lumière des outils RÉELLEMENT exécutés. But : cohérence factuelle + langue propre
# (aucun artefact non-français, aucun JSON/chemin/détail technique), prête pour le TTS.
VERIFY_SYSTEM = (
    "Tu es TURBO OS VERIFY, second cerveau de contrôle qualité. On te fournit : "
    "l'instruction de l'utilisateur, la trace des outils RÉELLEMENT exécutés "
    "(commande -> résultat réel), et la phrase finale proposée par l'exécuteur. "
    "Ta mission :\n"
    "1) VÉRIFIER que la phrase finale est EXACTE, cohérente avec les résultats réels "
    "des outils (ne rien affirmer qui contredise la trace ; ne rien inventer).\n"
    "RÈGLE CLÉ : un résultat d'outil EN ERREUR (rc non nul, stderr, TIMEOUT, EOF, "
    "« ERREUR », « REFUSÉ », commande malformée) N'EST PAS une preuve sur le sujet. "
    "Ex. : « systemctl is-active » qui échoue à s'exécuter ne prouve PAS que le service "
    "est arrêté. Dans ce cas, dis honnêtement que la vérification n'a pas pu aboutir "
    "— n'affirme jamais un état à partir d'une erreur.\n"
    "2) NETTOYER : elle doit être en français naturel, brève, SANS aucun caractère "
    "non-français (ex. idéogramme chinois), SANS JSON, SANS chemin de fichier, SANS "
    "détail technique brut, SANS balise — juste une réponse prête à être lue à voix haute.\n"
    "Si la phrase proposée est correcte et propre, renvoie-la telle quelle. Si elle est "
    "fausse, incomplète ou sale, RÉÉCRIS-la à partir des résultats réels des outils. "
    "Réponds UNIQUEMENT par la phrase finale, sans préambule, sans guillemets, sans commentaire."
)


def _clean_voice_text(text: str) -> str:
    """Nettoie une phrase destinée au TTS : retire le raisonnement <think> (qwen3),
    les fences de code, les guillemets encadrants et les espaces superflus."""
    if not text:
        return ""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S | re.I)
    text = re.sub(r"</?think>", "", text, flags=re.I)          # balise orpheline
    text = re.sub(r"```[a-zA-Z0-9]*", "", text)                 # fences markdown
    text = text.strip().strip("`").strip()
    if len(text) >= 2 and text[0] in "\"'«“" and text[-1] in "\"'»”":
        text = text[1:-1].strip()
    return text.strip()


def _verify(instruction: str, trace: list, proposed: str, verbose: bool = True) -> str:
    """Pass VERIFY (qwen3-8b) : relit/corrige la phrase finale avant vocalisation.
    Best-effort : en cas d'échec réseau/modèle, renvoie '' → l'appelant garde la
    phrase brute (nettoyée mécaniquement). Ne casse jamais le pipeline."""
    if trace:
        lines = []
        for t in trace[-6:]:                                   # 6 derniers outils = contexte suffisant
            res = str(t.get("result", ""))[:300]
            lines.append(f"- {t['tool']}({json.dumps(t.get('args', {}), ensure_ascii=False)}) -> {res}")
        trace_txt = "\n".join(lines)
    else:
        trace_txt = ("(AUCUN outil exécuté — tu n'as donc AUCUNE preuve. N'affirme NI ne "
                     "nie AUCUN état système/service. Reste prudent et factuel.)")
    user = (
        f"INSTRUCTION UTILISATEUR :\n{instruction}\n\n"
        f"OUTILS RÉELLEMENT EXÉCUTÉS (commande -> résultat réel) :\n{trace_txt}\n\n"
        f"PHRASE FINALE PROPOSÉE PAR L'EXÉCUTEUR :\n{proposed}\n\n"
        "Renvoie la phrase finale vérifiée et propre. /no_think"
    )
    try:
        resp = _post({"model": VERIFY_MODEL,
                      "messages": [{"role": "system", "content": VERIFY_SYSTEM},
                                   {"role": "user", "content": user}],
                      "temperature": 0, "max_tokens": 1024})
        out = _clean_voice_text(resp["choices"][0]["message"].get("content") or "")
        if verbose and out:
            flag = "≠ corrigée" if out.strip() != _clean_voice_text(proposed).strip() else "= validée"
            print(f"  ✅ VERIFY({VERIFY_MODEL}) {flag} -> {out[:120].strip()}")
        return out
    except Exception as e:
        if verbose:
            print(f"  ⚠️  VERIFY indisponible ({e}) -> phrase brute conservée")
        return ""


def run(instruction: str, speak_final: bool = True, verbose: bool = True,
        verify: bool = VERIFY_ENABLED, task_id: str = None, resume: bool = False) -> dict:
    import time as _t
    try:
        import checkpoint as _ck               # module voisin (checkpoint engine)
    except Exception:
        _ck = None
    if task_id is None:
        task_id = f"task-{os.getpid()}-{int(_t.time())}"
    messages = [
        {"role": "system", "content": _system_prompt()},
        {"role": "user", "content": instruction},
    ]
    trace = []
    if resume and _ck:                          # REPRISE : restaure au dernier pas sûr
        _s = _ck.restore(task_id)
        if _s and _s.get("state"):
            messages = _s["state"].get("messages", messages)
            trace = _s["state"].get("trace", trace)
            if verbose:
                print(f"  ⏯️  reprise du checkpoint {task_id} (étape {_s['state'].get('step')})")
    strict_retries = 0
    sig_counts = {}   # circuit breaker : compte les appels (outil+args) identiques

    def _breaker(name, args):
        """True si le même appel est répété ≥3× → stoppe la boucle infinie
        (cf. cockpit Qwen bloqué à réémettre le même script cassé)."""
        sig = name + "|" + json.dumps(args, sort_keys=True, ensure_ascii=False)
        sig_counts[sig] = sig_counts.get(sig, 0) + 1
        return sig_counts[sig] >= 3

    for step in range(MAX_TOOL_LOOPS):
        if _ck and _ck.is_cancelled(task_id):                       # CANCEL
            return {"status": "cancelled", "answer": "Tâche annulée proprement.",
                    "trace": trace, "task_id": task_id}
        if _ck and _ck.is_paused(task_id):                          # PAUSE + checkpoint
            _ck.save(task_id, {"objective": instruction, "step": step,
                               "trace": trace, "messages": messages}, "PAUSED")
            return {"status": "paused", "answer": "Tâche en pause — reprise possible au dernier pas.",
                    "trace": trace, "task_id": task_id, "step": step}
        resp = _post({"model": MODEL, "messages": messages, "tools": TOOL_SPECS,
                      "tool_choice": "auto", "temperature": 0, "max_tokens": 4096})
        if "choices" not in resp:
            return {"status": "error", "error": str(resp)[:300], "trace": trace}
        msg = resp["choices"][0]["message"]
        tool_calls = msg.get("tool_calls") or []

        if tool_calls:
            messages.append({"role": "assistant", "content": msg.get("content") or "",
                             "tool_calls": tool_calls})
            for tc in tool_calls:
                name = tc["function"]["name"]
                try:
                    args = json.loads(tc["function"]["arguments"] or "{}")
                except Exception:
                    args = {}
                if _breaker(name, args):
                    return {"status": "blocked", "trace": trace, "tool_loops": step + 1,
                            "answer": f"Boucle détectée : l'appel « {name} » a été répété 3× à "
                            f"l'identique sans progrès. Arrêt (circuit breaker)."}
                result = TOOLS.get(name, lambda **k: "TOOL_UNAVAILABLE")(**args)
                if verbose:
                    print(f"  🔧 {name}({args}) -> {result[:120].strip()}")
                trace.append({"tool": name, "args": args, "result": result[:500]})
                messages.append({"role": "tool", "tool_call_id": tc.get("id", name),
                                 "name": name, "content": str(result)})
            if _ck:                                                 # CHECKPOINT après chaque étape
                _ck.save(task_id, {"objective": instruction, "step": step,
                                   "trace": trace, "messages": messages}, "RUNNING")
            continue  # reboucle : le modèle lit les résultats et décide

        # pas de tool_call structuré -> essayer un tool call in-band (format Qwen)
        content = (msg.get("content") or "").strip()
        inband = _extract_inband_calls(content)
        if inband:
            messages.append({"role": "assistant", "content": content})
            for name, args in inband:
                if _breaker(name, args):
                    return {"status": "blocked", "trace": trace, "tool_loops": step + 1,
                            "answer": f"Boucle détectée : l'appel « {name} » a été répété 3× à "
                            f"l'identique sans progrès. Arrêt (circuit breaker)."}
                result = TOOLS.get(name, lambda **k: "TOOL_UNAVAILABLE")(**args)
                if verbose:
                    print(f"  🔧 (in-band) {name}({args}) -> {result[:120].strip()}")
                trace.append({"tool": name, "args": args, "result": result[:500]})
                messages.append({"role": "user",
                                 "content": f"[résultat {name}] {result}"})
            continue

        # réponse texte
        low = content.lower()
        is_narration = any(n in low for n in NARRATION)
        if is_narration and strict_retries < 2:
            strict_retries += 1
            if verbose:
                print(f"  ⚠️  WRONG_MODE détecté (narration) -> relance stricte #{strict_retries}")
            messages.append({"role": "assistant", "content": content})
            messages.append({"role": "user", "content":
                             "EXECUTE NOW. USE REAL TOOL. DO NOT EXPLAIN. "
                             "Appelle directement l'outil nécessaire, sans annoncer."})
            continue

        # Garde-fou anti-fabrication : contenu final = blob d'outil non exécuté
        # (trace vide) → NE PAS laisser VERIFY inventer un état système. Échec honnête.
        if not trace and _looks_like_tool_blob(content):
            final = ("Je n'ai pas pu exécuter l'action : le modèle a renvoyé un appel "
                     "d'outil malformé, non exécuté. Reformule ou relance la demande.")
            if verbose:
                print("  🛑 blob d'outil non exécuté + trace vide -> échec honnête (pas de fabrication VERIFY)")
            if speak_final:
                tool_speak(final)
            return {"status": "exec_failed", "answer": final, "raw_answer": content,
                    "verified": False, "verify_model": None, "trace": trace,
                    "tool_loops": step + 1, "wrong_mode_retries": strict_retries}

        # réponse finale — pass VERIFY (qwen3-8b) AVANT vocalisation
        final = content
        verified = False
        if verify and content:
            checked = _verify(instruction, trace, content, verbose=verbose)
            if checked:
                final, verified = checked, True
            else:
                final = _clean_voice_text(content)   # VERIFY KO → nettoyage mécanique
        else:
            final = _clean_voice_text(content)       # VERIFY off → nettoyage mécanique
        if speak_final and final:
            tool_speak(final)
        return {"status": "answered", "answer": final, "raw_answer": content,
                "verified": verified, "verify_model": VERIFY_MODEL if verify else None,
                "trace": trace, "tool_loops": step + 1,
                "wrong_mode_retries": strict_retries}

    return {"status": "blocked", "answer": "MAX_TOOL_LOOPS atteint", "trace": trace}


if __name__ == "__main__":
    args = list(sys.argv[1:])
    speak = "--no-speak" not in args
    verify = VERIFY_ENABLED and "--no-verify" not in args
    resume = "--resume" in args
    task_id = None
    if "--task" in args:
        i = args.index("--task"); task_id = args[i + 1]; del args[i:i + 2]
    args = [a for a in args if a not in ("--no-speak", "--no-verify", "--resume")]
    if not args and not resume:
        print("usage: jarvis_core_loop.py [--no-speak] [--no-verify] [--task ID] [--resume] \"<instruction>\"")
        sys.exit(2)
    out = run(" ".join(args), speak_final=speak, verify=verify, task_id=task_id, resume=resume)
    print("\n=== RÉSULTAT ===")
    print(json.dumps(out, ensure_ascii=False, indent=2))
