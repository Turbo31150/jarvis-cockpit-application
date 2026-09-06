#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Test fumée du moteur Table Ronde — inférence stubbée pour valider l'orchestration."""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import core.table_ronde_engine as tr


def fake_gen(prompt, sys_prompt="", max_tokens=256, temperature=0.3):
    persona = (sys_prompt.split(".")[0] or "expert")[:40]
    if "Président" in sys_prompt:
        return {"content": "CONVERGENCES : ok.\nTENSIONS : rien.\nDÉCISION : 1) agir.",
                "source": "STUB", "success": True, "latency": 0.01}
    return {"content": f"Avis simulé de [{persona}].", "source": "STUB", "success": True, "latency": 0.01}


tr.generate_completion = fake_gen
tr._infer_m1 = lambda *a, **k: {"success": False}
tr._infer_ollama = lambda *a, **k: {"success": False}

t = time.time()
r = tr.run_table_ronde_deliberation("Faut-il activer le mode portable ?",
                                    injecter_browser=False, injecter_board=True)
dt = round(time.time() - t, 2)

assert r["success"] is True, "success doit être True"
for k in ("content", "sources_count", "source", "deliberation", "consensus", "confidence"):
    assert k in r, f"clé manquante: {k}"
assert len(r["deliberation"]) == 7, f"attendu 7 experts, obtenu {len(r['deliberation'])}"
assert r["confidence"] == 100, f"confiance attendue 100, obtenue {r['confidence']}"
assert "CONVERGENCES" in r["consensus"], "consensus mal formé"

print(f"OK — 7 experts | clés GUI+web présentes | confiance {r['confidence']}% | latence {dt}s")
print(f"sources board FTS: {r['sources_count']}")
print("--- CONTENT (extrait) ---")
print(r["content"][:700])
print("... [tronqué]")
