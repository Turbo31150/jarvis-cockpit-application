#!/usr/bin/env python3
"""
scraping_pipeline.py — Pipeline enrichissement leads JARVIS
Fonctions :
- recherche_gouv(nom, departement)  → résultats API recherche-entreprises.api.gouv.fr
- enrichir_lead(siren)              → données complètes SIRENE
- scorer_lead(data)                 → applique règles TSV de prospection
- pipeline_complet(nom, dep)        → recherche + enrichissement + scoring
- sauver_cible_locale(cible)        → INSERT local Postgres
- sauver_cible_tour(cible)          → INSERT Tour via ssh jarvis-dva
"""

import json
import subprocess
import urllib.request
import urllib.parse
import urllib.error
import time

SIRENE_API = "https://recherche-entreprises.api.gouv.fr/search"
PAPPERS_API = "https://api.pappers.fr/v2/recherche"
USER_AGENT = "JarvisProspection/1.0 (local-cockpit)"
TIMEOUT = 8


# ─── Helpers HTTP ──────────────────────────────────────────────────────────────

def _get_json(url: str, params: dict = None, timeout: int = TIMEOUT) -> dict:
    """Requête GET JSON simple avec gestion d'erreurs."""
    if params:
        url = url + "?" + urllib.parse.urlencode({k: v for k, v in params.items() if v})
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return {"error": f"HTTP {e.code}: {e.reason}", "results": [], "total_results": 0}
    except Exception as e:
        return {"error": str(e), "results": [], "total_results": 0}


# ─── Recherche API gouv.fr ─────────────────────────────────────────────────────

def recherche_gouv(nom: str, departement: str = "", per_page: int = 10) -> list:
    """
    Recherche d'entreprises via l'API recherche-entreprises.api.gouv.fr.
    Retourne liste de dicts normalisés avec champs prospection.
    """
    params = {"q": nom, "per_page": per_page}
    if departement:
        params["departement"] = departement
    data = _get_json(SIRENE_API, params=params)
    if "error" in data and not data.get("results"):
        return [{"error": data["error"]}]
    resultats = []
    for r in data.get("results", []):
        siege = r.get("siege", {})
        dirigeants = r.get("dirigeants", [])
        dirigeant = ""
        if dirigeants:
            d0 = dirigeants[0]
            prenom = d0.get("prenom_usuel") or d0.get("prenom") or ""
            nom_d = d0.get("nom_patronyme") or d0.get("nom") or ""
            qualite = d0.get("qualite", "")
            dirigeant = f"{qualite} {prenom} {nom_d}".strip()
        resultats.append({
            "siren": r.get("siren", ""),
            "siret": siege.get("siret", ""),
            "nom": r.get("nom_complet", r.get("nom_raison_sociale", "")),
            "ville": siege.get("libelle_commune", siege.get("commune", "")),
            "code_postal": siege.get("code_postal", ""),
            "activite_principale": r.get("activite_principale", ""),
            "libelle_activite": r.get("libelle_activite_principale", ""),
            "tranche_effectif": r.get("tranche_effectif_salarie", ""),
            "date_creation": r.get("date_creation", ""),
            "dirigeant": dirigeant,
            "site_web": "",  # non disponible via cet endpoint
            "source": "gouv_sirene",
        })
    return resultats


def recherche_pappers(nom: str, departement: str = "", api_token: str = "") -> list:
    """
    Recherche d'entreprises via Pappers API (mode libre sans token limité).
    """
    params = {"q": nom, "par_page": 10}
    if departement:
        params["departement"] = departement
    if api_token:
        params["api_token"] = api_token
    data = _get_json(PAPPERS_API, params=params)
    if "error" in data:
        return [{"error": data["error"]}]
    resultats = []
    for r in data.get("resultats", []):
        dirigeants = r.get("dirigeants", [])
        dirigeant = ""
        if dirigeants:
            d0 = dirigeants[0]
            dirigeant = f"{d0.get('qualite','')} {d0.get('prenom','')} {d0.get('nom','')}".strip()
        resultats.append({
            "siren": r.get("siren", ""),
            "siret": r.get("siege", {}).get("siret", ""),
            "nom": r.get("nom_entreprise", ""),
            "ville": r.get("siege", {}).get("ville", ""),
            "code_postal": r.get("siege", {}).get("code_postal", ""),
            "activite_principale": r.get("code_naf", ""),
            "libelle_activite": r.get("libelle_code_naf", ""),
            "tranche_effectif": str(r.get("effectif", "")),
            "date_creation": r.get("date_creation", ""),
            "dirigeant": dirigeant,
            "site_web": r.get("site_web", ""),
            "source": "pappers",
        })
    return resultats


def enrichir_lead(siren: str) -> dict:
    """Enrichit un SIREN avec les données complètes de l'API gouv."""
    if not siren:
        return {"error": "SIREN vide"}
    resultats = recherche_gouv(siren)
    for r in resultats:
        if r.get("siren") == siren or not r.get("error"):
            return r
    return resultats[0] if resultats else {"error": "Non trouvé"}


# ─── Scoring déterministe ──────────────────────────────────────────────────────

def scorer_lead(data: dict) -> dict:
    """
    Applique les règles TSV de prospection sur les données d'un lead.
    Retourne data enrichi avec segment, score, priorite, action_recommandee.
    """
    try:
        from core.prospection_engine import charger_regles_prospection, qualifier_prospect
    except ImportError:
        try:
            from prospection_engine import charger_regles_prospection, qualifier_prospect
        except ImportError:
            data.update({"segment": "non_route", "score": 0, "priorite": "🌱 VEILLE",
                         "action_recommandee": "Qualifier manuellement", "processus_qui_saigne": ""})
            return data

    # Construire le texte de qualification
    texte_parts = [
        data.get("nom", ""),
        data.get("libelle_activite", ""),
        data.get("activite_principale", ""),
        data.get("dirigeant", ""),
        data.get("site_web", ""),
        data.get("ville", ""),
    ]
    texte = " ".join(p for p in texte_parts if p)

    regles = charger_regles_prospection()
    prospect = {
        "entreprise": data.get("nom", ""),
        "texte": texte,
        "segment": "",
        "ville": data.get("ville", ""),
        "dirigeant": data.get("dirigeant", ""),
        "siren": data.get("siren", ""),
        "site_web": data.get("site_web", ""),
        "source_url": data.get("source", ""),
    }

    qualification = qualifier_prospect(prospect, regles)
    data.update({
        "segment": qualification.get("segment", "non_route"),
        "score": qualification.get("score", 0),
        "processus_qui_saigne": qualification.get("processus_qui_saigne", ""),
        "priorite": qualification.get("priorite", "🌱 VEILLE"),
        "action_recommandee": qualification.get("action_recommandee", "Veille"),
    })
    return data


# ─── Pipeline complet ──────────────────────────────────────────────────────────

def pipeline_complet(nom: str, departement: str = "", sauver_local: bool = False,
                     sauver_tour: bool = False) -> list:
    """
    Pipeline complet : recherche SIRENE → scoring déterministe → tri par score.
    Optionnellement sauvegarde dans Postgres local et/ou Tour.
    """
    leads = recherche_gouv(nom, departement)
    if leads and leads[0].get("error"):
        return leads

    scored = []
    for lead in leads:
        lead_score = scorer_lead(lead)
        scored.append(lead_score)
        if sauver_local and lead_score.get("score", 0) > 0:
            sauver_cible_locale(lead_score)
        if sauver_tour and lead_score.get("score", 0) > 0:
            sauver_cible_tour(lead_score)

    scored.sort(key=lambda x: x.get("score", 0), reverse=True)
    return scored


# ─── Sauvegarde Postgres ───────────────────────────────────────────────────────

def _build_insert_sql(cible: dict) -> str:
    """Génère la requête SQL d'insertion."""
    entreprise = cible.get("nom", "").replace("'", "''")
    ville = cible.get("ville", "").replace("'", "''")
    segment = cible.get("segment", "non_route").replace("'", "''")
    score = int(cible.get("score", 0))
    processus = cible.get("processus_qui_saigne", "").replace("'", "''")
    dirigeant = cible.get("dirigeant", "").replace("'", "''")
    siren = cible.get("siren", "").replace("'", "''")
    statut = "nouveau"
    source = cible.get("source", "sirene_api").replace("'", "''")

    return (
        f"INSERT INTO prospection.cibles "
        f"(entreprise, ville, segment, score, processus_qui_saigne, dirigeant, statut, mots_declencheurs) "
        f"VALUES ('{entreprise}', '{ville}', '{segment}', {score}, '{processus}', '{dirigeant}', '{statut}', '{siren}') "
        f"ON CONFLICT (cle_naturelle) DO UPDATE SET score={score}, statut=EXCLUDED.statut "
        f"WHERE prospection.cibles.score < {score};"
    )


def sauver_cible_locale(cible: dict) -> bool:
    """INSERT dans prospection.cibles via docker exec jarvis-postgres (Postgres local)."""
    sql = _build_insert_sql(cible)
    try:
        subprocess.check_output(
            ["docker", "exec", "-i", "jarvis-postgres", "psql",
             "-U", "jarvis", "-d", "jarvis_main", "-c", sql],
            text=True, timeout=5, stderr=subprocess.DEVNULL
        )
        return True
    except Exception:
        return False


def sauver_cible_tour(cible: dict) -> bool:
    """INSERT dans prospection.cibles Tour via ssh jarvis-dva → ssh root@100.124.69.1."""
    sql = _build_insert_sql(cible).replace('"', '\\"')
    cmd_remote = f"ssh -o ConnectTimeout=4 -o BatchMode=yes root@100.124.69.1 \"docker exec jarvis-postgres psql -U jarvis -d jarvis_main -c '{sql}'\""
    try:
        subprocess.check_output(
            ["ssh", "-o", "ConnectTimeout=4", "-o", "BatchMode=yes", "jarvis-dva", cmd_remote],
            text=True, timeout=10, stderr=subprocess.DEVNULL
        )
        return True
    except Exception:
        return False


def batch_pipeline_depuis_csv(lignes: list) -> list:
    """
    Traite un batch de lignes (dicts) comme entrées du pipeline.
    Compatible avec le format router.py de Rémi.
    """
    resultats = []
    for ligne in lignes:
        nom = ligne.get("entreprise") or ligne.get("nom") or ligne.get("denomination") or ""
        dep = ligne.get("departement") or ligne.get("code_postal", "")[:2] or ""
        if not nom:
            continue
        lead = {**ligne, "nom": nom}
        lead_score = scorer_lead(lead)
        resultats.append(lead_score)
    resultats.sort(key=lambda x: x.get("score", 0), reverse=True)
    return resultats
