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


def offline_gen(prompt, sys_prompt="", max_tokens=256, temperature=0.3):
    """Scénario hors-ligne : aucun moteur ne répond."""
    return {"success": False}


# ── Scénario 1 : chemin nominal (LLM mocké qui RÉPOND) ──────────────────────
tr.generate_completion = fake_gen
tr._infer_m1 = lambda *a, **k: {"success": False}
tr._infer_ollama = lambda *a, **k: {"success": False}

t = time.time()
r = tr.run_table_ronde_deliberation("Faut-il activer le mode portable ?",
                                    injecter_browser=False, injecter_board=True)
dt = round(time.time() - t, 2)

assert r["success"] is True, "success doit être True"
for k in ("content", "sources_count", "source", "deliberation", "consensus", "confidence", "moteurs_distincts"):
    assert k in r, f"clé manquante: {k}"
assert len(r["deliberation"]) == 7, f"attendu 7 experts, obtenu {len(r['deliberation'])}"
assert r["confidence"] == 100, f"confiance attendue 100, obtenue {r['confidence']}"
assert "CONVERGENCES" in r["consensus"], "consensus mal formé"
# Le mock ne fournit qu'UN moteur (STUB) → la dégradation mono-moteur doit être signalée
assert r["moteurs_distincts"] == ["STUB"], f"moteurs attendus [STUB], obtenu {r['moteurs_distincts']}"
assert "Diversité limitée" in r["content"], "l'alerte diversité mono-moteur doit apparaître"

# ── Scénario 2 : chemin dégradé (tous moteurs hors-ligne) → confiance 0 ──────
tr.generate_completion = offline_gen
r2 = tr.run_table_ronde_deliberation("Question hors-ligne ?",
                                     injecter_browser=False, injecter_board=False)
assert r2["success"] is True, "l'orchestration doit rester robuste hors-ligne"
assert r2["confidence"] == 0, f"hors-ligne → confiance 0 attendue, obtenue {r2['confidence']}"
assert r2["moteurs_distincts"] == [], "aucun moteur réel ne doit être compté hors-ligne"
assert all(not d["reel"] for d in r2["deliberation"]), "tous les avis doivent être en repli"

print(f"OK scénario nominal (mock) — 7 experts | confiance {r['confidence']}% | 1 moteur mocké | latence {dt}s")
print(f"OK scénario hors-ligne — confiance {r2['confidence']}% | 0 moteur réel | repli propre")
print(f"sources board FTS: {r['sources_count']}")
print("--- CONTENT nominal (extrait) ---")
print(r["content"][:600])
print("... [tronqué]")
