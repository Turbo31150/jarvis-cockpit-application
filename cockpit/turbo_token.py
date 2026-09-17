#!/usr/bin/env python3
"""turbo-token — émetteur de tokens d'accès Turbo OS (comme ssh-keygen).

Un token = une clé d'accès délivrée par le PROPRIÉTAIRE à un installeur. Il sert de passerelle :
l'installation distante se connecte, via ce token, directement à CE cockpit.

Propriétés : accès limité (scope), durée de validité (TTL), révocable. Registre VIDE par défaut
(zero-trust : personne n'a accès tant qu'aucun token n'est créé).

CLI :
  turbo-token create --label "Cabinet Durand" --scope orbe --ttl 7d   # imprime le token UNE fois
  turbo-token list
  turbo-token revoke <id>
  turbo-token verify <token> [--scope orbe]

Import (côté cockpit) : from turbo_token import verify ; verify(token, scope="orbe")
"""
from __future__ import annotations
import argparse, datetime, hashlib, json, os, secrets, time

REG = os.path.expanduser("~/jarvis/data/turbo_tokens.json")


def _load() -> list:
    try:
        with open(REG, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def _save(d: list) -> None:
    os.makedirs(os.path.dirname(REG), exist_ok=True)
    tmp = REG + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)
    os.replace(tmp, REG)
    try:
        os.chmod(REG, 0o600)
    except Exception:
        pass


def _h(t: str) -> str:
    return hashlib.sha256(t.encode()).hexdigest()


def _ttl_seconds(s: str) -> int:
    """'7d' '24h' '30m' '90s' '0'/'' = illimité."""
    if not s or s == "0":
        return 0
    unit = s[-1].lower()
    if unit.isdigit():
        return int(s)
    return int(s[:-1]) * {"d": 86400, "h": 3600, "m": 60, "s": 1}.get(unit, 86400)


def verify(token: str, scope: str | None = None, now: int | None = None) -> dict:
    """Valide un token : existence, non révoqué, non expiré, scope autorisé."""
    if not token:
        return {"ok": False, "reason": "missing"}
    now = now or int(time.time())
    for e in _load():
        if e.get("token_sha256") == _h(token):
            if e.get("revoked"):
                return {"ok": False, "reason": "revoked", "id": e.get("id")}
            exp = e.get("expires", 0)
            if exp and now > exp:
                return {"ok": False, "reason": "expired", "id": e.get("id")}
            if scope and e.get("scope") not in ("*", scope):
                return {"ok": False, "reason": "scope", "id": e.get("id")}
            return {"ok": True, "id": e.get("id"), "label": e.get("label"),
                    "scope": e.get("scope"), "expires": exp}
    return {"ok": False, "reason": "unknown"}


def create(label: str, scope: str, ttl: str) -> tuple[str, dict]:
    d = _load()
    token = "tok_" + secrets.token_hex(24)
    now = int(time.time())
    ttls = _ttl_seconds(ttl)
    e = {"id": secrets.token_hex(4), "label": label or "sans-nom", "scope": scope or "orbe",
         "token_sha256": _h(token), "created": now, "expires": (now + ttls if ttls else 0),
         "revoked": False}
    d.append(e)
    _save(d)
    return token, e


def list_public() -> list:
    """Liste des accès SANS les empreintes (pour affichage / HTTP / gérance cockpit)."""
    now = int(time.time())
    out = []
    for e in _load():
        exp = e.get("expires", 0)
        st = "revoked" if e.get("revoked") else ("expired" if exp and now > exp else "valid")
        out.append({"id": e.get("id"), "label": e.get("label"), "scope": e.get("scope"),
                    "created": e.get("created"), "expires": exp, "state": st})
    return out


def revoke(token_id: str) -> bool:
    d = _load()
    for e in d:
        if e.get("id") == token_id:
            e["revoked"] = True
            _save(d)
            return True
    return False


def _fmt(ts: int) -> str:
    return "illimité" if not ts else datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")


def main() -> int:
    p = argparse.ArgumentParser(description="Émetteur de tokens d'accès Turbo OS")
    sub = p.add_subparsers(dest="cmd")
    c = sub.add_parser("create", help="créer un token")
    c.add_argument("--label", default="sans-nom")
    c.add_argument("--scope", default="orbe", help="portée (orbe, admin, *)")
    c.add_argument("--ttl", default="7d", help="validité: 7d/24h/30m/0(illimité)")
    sub.add_parser("list", help="lister les tokens")
    r = sub.add_parser("revoke", help="révoquer un token")
    r.add_argument("id")
    v = sub.add_parser("verify", help="vérifier un token")
    v.add_argument("token")
    v.add_argument("--scope", default=None)
    a = p.parse_args()

    if a.cmd == "create":
        tok, e = create(a.label, a.scope, a.ttl)
        print(f"✅ Token créé  id={e['id']}  scope={e['scope']}  expire={_fmt(e['expires'])}")
        print("⚠️  Copie-le maintenant, il ne sera plus affiché :\n")
        print(f"    {tok}\n")
        return 0
    if a.cmd == "list":
        d = _load()
        if not d:
            print("Registre VIDE — aucun accès délivré (zero-trust).")
            return 0
        now = int(time.time())
        for e in d:
            exp = e.get("expires", 0)
            st = "révoqué" if e.get("revoked") else ("expiré" if exp and now > exp else "valide")
            print(f"  {e['id']}  [{st:8}] scope={e.get('scope'):6} exp={_fmt(exp):16} {e.get('label')}")
        return 0
    if a.cmd == "revoke":
        d = _load()
        for e in d:
            if e.get("id") == a.id:
                e["revoked"] = True
                _save(d)
                print(f"🚫 Token {a.id} révoqué.")
                return 0
        print(f"id {a.id} introuvable.")
        return 1
    if a.cmd == "verify":
        print(json.dumps(verify(a.token, a.scope), ensure_ascii=False))
        return 0
    p.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
