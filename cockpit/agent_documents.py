#!/usr/bin/env python3
"""agent_documents — agent spécialisé Turbo OS (OMEGA) : DOCUMENTS & FACTURATION ÉLECTRONIQUE.

Orchestre sa propre chaîne : fichier → (OCR tesseract via passcerfa) → détection CERFA →
extraction des champs → flag facture (→ Factur-X disponible). Réutilise les services passcerfa.

API : traiter_fichier(b64=..., filename=...) ou traiter_fichier(path=...) → dict JSON.
"""
from __future__ import annotations
import base64
import json
import os
import subprocess
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
BRIDGE = os.path.join(_HERE, "passcerfa_bridge.js")


def traiter_fichier(path: str | None = None, b64: str | None = None, filename: str = "document") -> dict:
    tmp = None
    try:
        if b64:
            try:
                data = base64.b64decode(b64.split(",")[-1])
            except Exception as e:
                return {"ok": False, "error": f"base64 invalide: {e}"}
            ext = os.path.splitext(filename)[1] or ".bin"
            fd, tmp = tempfile.mkstemp(suffix=ext, prefix="turbo-doc-", dir="/tmp")
            os.close(fd)
            with open(tmp, "wb") as f:
                f.write(data)
            path = tmp
        if not path or not os.path.exists(path):
            return {"ok": False, "error": "fichier absent"}
        r = subprocess.run(["node", BRIDGE, path], capture_output=True, text=True, timeout=90)
        out = (r.stdout or "").strip()
        if out.startswith("{"):
            res = json.loads(out)
        else:
            return {"ok": False, "error": (r.stderr or out or "pont sans sortie")[:300]}
        # Résumé humain (pour la voix / la bulle)
        det = res.get("detected")
        if res.get("facture"):
            res["resume"] = "Facture détectée — génération Factur-X (EN 16931) disponible."
        elif det:
            res["resume"] = f"Document reconnu : {det['label']} (CERFA {det['cerfa']}, confiance {det['confidence']})."
        else:
            res["resume"] = "Document lu ; type non reconnu dans le registre."
        res["agent"] = "documents/facturation"
        return res
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "traitement trop long (timeout)"}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}
    finally:
        if tmp and os.path.exists(tmp):
            try:
                os.remove(tmp)
            except Exception:
                pass


if __name__ == "__main__":
    import sys
    print(json.dumps(traiter_fichier(path=sys.argv[1] if len(sys.argv) > 1 else None), ensure_ascii=False, indent=2))
