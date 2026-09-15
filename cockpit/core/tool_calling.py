#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JARVIS COCKPIT — TOOL-CALLING ENGINE (function calling LM Studio)

Comble le gap P1 de la cartographie 2026-09-15 : core/inference.py fait de la
complétion pure (aucune clé "tools" envoyée au LLM). Ce module ajoute une
boucle de function-calling OpenAI-compatible contre LM Studio (:1234) :

    LLM(tools) -> tool_calls -> executor(name,args) -> résultat réinjecté -> LLM -> ... -> réponse finale

Additif et non destructif : n'importe AUCUN fichier existant du cockpit, ne
modifie pas serveur.py. Peut être câblé plus tard à une route /api/chat/tools.

Auto-test :  python3 core/tool_calling.py
"""

import json
import time
import sqlite3
import urllib.request

# --- prompt d'exécution court (leçon cartographie : un 7B obéit à un prompt court) ---
EXECUTION_SYS = (
    "Tu es l'agent d'exécution local de JARVIS. Pour toute inspection ou action, "
    "APPELLE l'outil correspondant via le mécanisme de tool call — n'écris jamais "
    "l'appel en JSON dans ta réponse. Lis le résultat de l'outil puis réponds de "
    "façon concise. N'invente jamais un chemin, une table ou un résultat."
)

_LM_BASES = ("http://127.0.0.1:1234", "http://192.168.42.241:1234")


def _lm_base(timeout: float = 0.6):
    """Première base LM Studio joignable (loopback puis IP tether USB)."""
    for base in _LM_BASES:
        try:
            urllib.request.urlopen(base + "/v1/models", timeout=timeout).read()
            return base
        except Exception:
            continue
    return None


def _lm_model(base: str, timeout: float = 3.0):
    """1er modèle non-embedding exposé par LM Studio."""
    try:
        data = json.loads(urllib.request.urlopen(base + "/v1/models", timeout=timeout).read().decode())
        for m in data.get("data", []):
            mid = m.get("id", "")
            if "embed" not in mid.lower():
                return mid
    except Exception:
        pass
    return None


def generate_with_tools(prompt, tools, executor, sys_prompt=EXECUTION_SYS,
                        model=None, max_rounds=4, temperature=0.2, max_tokens=1024,
                        base=None):
    """
    Boucle de function-calling contre LM Studio.
      tools    : liste OpenAI [{type:function, function:{name,description,parameters}}]
      executor : callable(name:str, args:dict) -> objet JSON-sérialisable
    Retour: {success, content, model, rounds, trace:[{tool,args,result_preview}], ...}
    """
    base = base or _lm_base()
    if not base:
        return {"success": False, "error": "LM Studio injoignable (:1234)"}
    model = model or _lm_model(base)
    if not model:
        return {"success": False, "error": "aucun modèle de complétion exposé"}

    messages = [{"role": "system", "content": sys_prompt},
                {"role": "user", "content": prompt}]
    trace = []
    sig_counts = {}   # circuit breaker anti-boucle (même appel outil+args répété)
    t0 = time.time()

    for rnd in range(max_rounds):
        payload = json.dumps({
            "model": model, "messages": messages,
            "tools": tools, "tool_choice": "auto",
            "temperature": temperature, "max_tokens": max_tokens,
        }).encode("utf-8")
        req = urllib.request.Request(base + "/v1/chat/completions", data=payload,
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                msg = json.loads(resp.read().decode())["choices"][0]["message"]
        except Exception as e:
            return {"success": False, "error": f"appel LM Studio: {e}", "trace": trace}

        tool_calls = msg.get("tool_calls")
        if not tool_calls:
            content = (msg.get("content") or "").strip()
            if "</think>" in content:
                content = content.split("</think>")[-1].strip()
            return {"success": True, "content": content, "model": model,
                    "rounds": rnd + 1, "trace": trace,
                    "latency": round(time.time() - t0, 2)}

        # rejoue l'assistant (avec ses tool_calls) puis exécute chaque outil
        messages.append({"role": "assistant", "content": msg.get("content") or "",
                         "tool_calls": tool_calls})
        for tc in tool_calls:
            fn = tc.get("function", {})
            name = fn.get("name", "")
            try:
                args = json.loads(fn.get("arguments") or "{}")
            except Exception:
                args = {}
            _sig = name + "|" + json.dumps(args, sort_keys=True, ensure_ascii=False)
            sig_counts[_sig] = sig_counts.get(_sig, 0) + 1
            if sig_counts[_sig] >= 3:
                return {"success": False, "blocked": True, "model": model,
                        "rounds": rnd + 1, "trace": trace,
                        "content": f"Boucle détectée : « {name} » répété 3× à l'identique. "
                        "Arrêt (circuit breaker).",
                        "latency": round(time.time() - t0, 2)}
            try:
                result = executor(name, args)
            except Exception as e:
                result = {"error": f"executor: {e}"}
            trace.append({"tool": name, "args": args, "result_preview": str(result)[:300]})
            messages.append({"role": "tool", "tool_call_id": tc.get("id"),
                             "content": json.dumps(result, ensure_ascii=False)[:4000]})

    return {"success": True, "content": "[max_rounds atteint sans réponse finale]",
            "model": model, "rounds": max_rounds, "trace": trace, "incomplete": True,
            "latency": round(time.time() - t0, 2)}


# ---------------------------------------------------------------------------
# Jeu d'outils READ-ONLY de démonstration (sûr, aucune mutation)
# ---------------------------------------------------------------------------
SAFE_TOOLS = [
    {"type": "function", "function": {
        "name": "list_sql_tables",
        "description": "Liste les tables d'une base SQLite (lecture seule).",
        "parameters": {"type": "object",
                       "properties": {"db_path": {"type": "string"}},
                       "required": ["db_path"]}}},
    {"type": "function", "function": {
        "name": "count_rows",
        "description": "Compte les lignes d'une table SQLite (lecture seule).",
        "parameters": {"type": "object",
                       "properties": {"db_path": {"type": "string"}, "table": {"type": "string"}},
                       "required": ["db_path", "table"]}}},
]


def _t_list_sql_tables(db_path):
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        rows = con.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
        return {"tables": [r[0] for r in rows]}
    finally:
        con.close()


def _t_count_rows(db_path, table):
    if not table.replace("_", "").isalnum():
        return {"error": "nom de table invalide"}
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        return {"table": table, "count": con.execute(f"SELECT count(*) FROM {table}").fetchone()[0]}
    finally:
        con.close()


def safe_executor(name, args):
    if name == "list_sql_tables":
        return _t_list_sql_tables(args["db_path"])
    if name == "count_rows":
        return _t_count_rows(args["db_path"], args["table"])
    return {"error": f"TOOL_UNAVAILABLE: {name}"}


if __name__ == "__main__":
    print("== Auto-test tool-calling cockpit (LM Studio) ==")
    q = "Quelles tables contient la base /home/turbo/jarvis/jarvis_master.db, et combien de lignes dans la table tasks ?"
    r = generate_with_tools(q, SAFE_TOOLS, safe_executor, max_rounds=4)
    print(json.dumps(r, ensure_ascii=False, indent=2))
    ok = r.get("success") and r.get("trace") and any(t["tool"] == "list_sql_tables" for t in r["trace"])
    print("\nRESULT:", "✅ TOOL-CALLING OPÉRATIONNEL" if ok else "❌ échec")
