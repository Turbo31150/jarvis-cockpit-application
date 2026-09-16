#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JARVIS COCKPIT — MOTEUR DE PROSPECTION & INTELLIGENCE SOURCES CONSOLIDÉ
======================================================================
Inspiré de l'architecture éprouvée de Rémi (rem-linux : tunnels SSH/Tailscale,
qualification déterministe à 0 token, règles par "processus qui saigne") et enrichi
par les standards web souverains 2026 (API Open Data SIRENE / INPI, crawler
anti-bruit déterministe, et synthèse par modèles locaux LM Studio / Ollama Rémi).
"""

import os
import re
import json
import sqlite3
import unicodedata
import subprocess
import urllib.request
import urllib.parse
from datetime import datetime
from pathlib import Path

HOME = Path.home()
JARVIS_DIR = HOME / "jarvis"
DATA_DIR = JARVIS_DIR / "data"
DB_PATH = DATA_DIR / "prospection_reelle.db"
CATALOGUE_PATH = DATA_DIR / "cibles_toulouse.tsv"
REGLES_PATH = DATA_DIR / "regles_prospection.tsv"

CHEMINS_MOISSON = [
    "/contact", "/contact-us", "/nous-contacter", "/fr/contact",
    "/mentions-legales", "/legal-notice", "/presse", "/press",
    "/equipe", "/team", "/about-us", "/a-propos", "/carrieres", ""
]

RE_MAIL = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
BRUIT = re.compile(
    r"(sentry|wixpress|example\.|exemple\.|\.png|\.jpg|\.jpeg|\.svg|\.gif|"
    r"@2x|godaddy|cloudflare|domain\.tld|votre@|your@|nom@|name@|user@|"
    r"sentry\.io|w3\.org|schema\.org)", re.I
)

URL_API_GOUV = "https://recherche-entreprises.api.gouv.fr/search"
REMI_OLLAMA_URL = "http://127.0.0.1:11500"
REMI_COCKPIT_URL = "http://127.0.0.1:8601"
REMI_TOKEN = "5fd517241556e9026a0b6914bf2766ae5fb8767808facccfab5cb865b0a78d40"
LOCAL_LMSTUDIO_URL = "http://127.0.0.1:1234/v1"


def normaliser(texte: str) -> str:
    """Normalise un texte : minuscules, suppression des accents et ponctuation."""
    if not texte:
        return ""
    texte = unicodedata.normalize("NFKD", texte)
    texte = "".join(c for c in texte if not unicodedata.combining(c))
    return texte.lower()


def init_db():
    """Initialise et migre la base de prospection avec les colonnes de qualification."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS contacts_moissonnes (
            id INTEGER PRIMARY KEY,
            entreprise TEXT NOT NULL,
            pole TEXT,
            email TEXT,
            formulaire_url TEXT,
            url_source TEXT NOT NULL,
            moissonne_le TEXT NOT NULL,
            UNIQUE(entreprise, email, url_source)
        );
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS moisson_journal (
            id INTEGER PRIMARY KEY,
            entreprise TEXT,
            url TEXT,
            http INTEGER,
            mails INTEGER,
            horodatage TEXT
        );
    """)
    # Migration progressive non-destructive
    cur.execute("PRAGMA table_info(contacts_moissonnes);")
    cols = [r[1] for r in cur.fetchall()]
    colonnes_a_ajouter = [
        ("segment", "TEXT"),
        ("processus_qui_saigne", "TEXT"),
        ("score", "INTEGER DEFAULT 0"),
        ("siret", "TEXT"),
        ("dirigeant", "TEXT"),
        ("statut", "TEXT DEFAULT 'QUALIFIE'")
    ]
    for col_nom, col_type in colonnes_a_ajouter:
        if col_nom not in cols:
            try:
                cur.execute(f"ALTER TABLE contacts_moissonnes ADD COLUMN {col_nom} {col_type};")
            except Exception:
                pass

    conn.commit()
    conn.close()


def contient(texte: str, motif: str) -> bool:
    """Mots courts (<=4 caractères) : frontière stricte, sinon substring pour les expressions."""
    if len(motif) <= 4:
        return re.search(r"(?<![a-z0-9])%s(?![a-z0-9])" % re.escape(motif), texte) is not None
    return motif in texte


def charger_regles_prospection() -> tuple[list[dict], dict]:
    """
    Charge les règles déterministes et bonus depuis regles_prospection.tsv (modèle Rémi).
    """
    regles = []
    bonus = {"dirigeant_connu": 10, "site_web": 5, "source_url": 5, "siret_connu": 8}
    
    if not REGLES_PATH.exists():
        return regles, bonus
        
    with open(REGLES_PATH, "r", encoding="utf-8") as f:
        for ligne in f:
            ligne = ligne.strip()
            if not ligne or ligne.startswith("#"):
                continue
            if ligne.startswith("!bonus"):
                parties = ligne.split("\t")
                if len(parties) >= 3 and parties[2].strip().isdigit():
                    bonus[parties[1].strip()] = int(parties[2].strip())
                continue
            parts = ligne.split("\t")
            if len(parts) >= 4:
                seg = parts[0].strip()
                if seg.lower() in ("segment", "header"):
                    continue
                poids = int(parts[1].strip()) if parts[1].strip().isdigit() else 50
                mots = [normaliser(m) for m in parts[2].split("|") if m.strip()]
                saigne = parts[3].strip()
                exclusions = [normaliser(m) for m in (parts[4].split("|") if len(parts) > 4 else []) if m.strip()]
                
                regles.append({
                    "segment": seg,
                    "poids": poids,
                    "mots": mots,
                    "processus_qui_saigne": saigne,
                    "exclusions": exclusions
                })
    return regles, bonus


def qualifier_prospect(texte: str, infos: dict = None) -> dict:
    """
    Routage déterministe à 0 token inspiré du moteur router.py de Rémi.
    Calcule le segment gagnant par détection de mots-clés, exclusions et bonus.
    """
    regles, bonus = charger_regles_prospection()
    infos = infos or {}
    t_norm = normaliser(texte)
    
    meilleur, touches_gagnantes = None, []
    for r in regles:
        if any(contient(t_norm, x) for x in r["exclusions"]):
            continue
        touches = [m for m in r["mots"] if contient(t_norm, m)]
        if not touches:
            continue
        cle = (len(touches), r["poids"])
        if meilleur is None or cle > (len(touches_gagnantes), meilleur["poids"]):
            meilleur, touches_gagnantes = r, touches
            
    if meilleur is None:
        return {
            "segment": "non_route",
            "score": 0,
            "occurrences": [],
            "processus_qui_saigne": "la gestion administrative manuelle et le manque d'automatisation des flux métiers récurrents",
            "priorite": "🌱 VEILLE",
            "action_recommandee": "Recherche complémentaire SIRENE ou ré-assignation manuelle",
            "qualifie": False
        }
        
    score = meilleur["poids"] + (len(touches_gagnantes) * 5)
    if infos.get("dirigeant"):
        score += bonus.get("dirigeant_connu", 10)
    if infos.get("url") or infos.get("site_web"):
        score += bonus.get("site_web", 5)
    if infos.get("siret") or infos.get("siren"):
        score += bonus.get("siret_connu", 8)

    if score >= 90:
        priorite = "🔥 CHAUD"
        action = "Appel direct ou démo on-premise dédiée"
    elif score >= 60:
        priorite = "⚡ TIÈDE"
        action = "Email d'accroche ciblé sur le processus qui saigne"
    else:
        priorite = "🌱 VEILLE"
        action = "Veille concurrentielle & enrichissement SIRENE"
        
    return {
        "segment": meilleur["segment"],
        "score": score,
        "occurrences": touches_gagnantes,
        "processus_qui_saigne": meilleur["processus_qui_saigne"],
        "poids_base": meilleur["poids"],
        "priorite": priorite,
        "action_recommandee": action,
        "qualifie": True
    }


def verifier_tunnels():
    """Vérifie l'état complet des tunnels Rémi et des moteurs locaux."""
    statut = {
        "tunnel_remi_ollama": False,
        "tunnel_remi_models": [],
        "tunnel_remi_cockpit": False,
        "tunnel_remi_cockpit_details": {},
        "lmstudio_local": False,
        "lmstudio_models": []
    }
    
    # 1. Tunnel Ollama Rémi (:11500)
    try:
        req = urllib.request.Request(f"{REMI_OLLAMA_URL}/api/tags", headers={"User-Agent": "JarvisCockpit/1.0"})
        with urllib.request.urlopen(req, timeout=2.0) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                statut["tunnel_remi_ollama"] = True
                statut["tunnel_remi_models"] = [m["name"] for m in data.get("models", [])]
    except Exception:
        pass

    # 2. Tunnel Cockpit Rémi (:8601)
    try:
        req = urllib.request.Request(
            f"{REMI_COCKPIT_URL}/api/status",
            headers={"User-Agent": "JarvisCockpit/1.0", "Authorization": f"Bearer {REMI_TOKEN}"}
        )
        with urllib.request.urlopen(req, timeout=2.0) as resp:
            if resp.status == 200:
                statut["tunnel_remi_cockpit"] = True
                statut["tunnel_remi_cockpit_details"] = json.loads(resp.read().decode("utf-8"))
    except Exception:
        pass

    # 3. LM Studio local (:1234)
    try:
        req = urllib.request.Request(f"{LOCAL_LMSTUDIO_URL}/models", headers={"User-Agent": "JarvisCockpit/1.0"})
        with urllib.request.urlopen(req, timeout=2.0) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                statut["lmstudio_local"] = True
                statut["lmstudio_models"] = [m["id"] for m in data.get("data", [])]
    except Exception:
        pass

    return statut


def lire_catalogue():
    """Lit le catalogue TSV des cibles et enrichit dynamiquement avec la qualification."""
    if not CATALOGUE_PATH.exists():
        return []
    cibles = []
    with open(CATALOGUE_PATH, "r", encoding="utf-8") as f:
        for ligne in f:
            ligne = ligne.strip()
            if not ligne or ligne.startswith("#"):
                continue
            parties = ligne.split("\t")
            if len(parties) >= 3:
                nom = parties[0].strip()
                pole = parties[1].strip()
                url = parties[2].strip()
                qualif = qualifier_prospect(f"{nom} {pole}", {"url": url})
                cibles.append({
                    "nom": nom,
                    "pole": pole,
                    "url": url,
                    "segment": qualif["segment"],
                    "processus_qui_saigne": qualif["processus_qui_saigne"],
                    "score": qualif["score"]
                })
    return cibles


def ajouter_cible_catalogue(nom: str, pole: str, url: str) -> bool:
    """Ajoute une cible au catalogue TSV si elle n'existe pas déjà."""
    cibles = lire_catalogue()
    for c in cibles:
        if c["nom"].lower() == nom.lower() or c["url"].rstrip("/").lower() == url.rstrip("/").lower():
            return False
    with open(CATALOGUE_PATH, "a", encoding="utf-8") as f:
        f.write(f"{nom}\t{pole}\t{url}\n")
    return True


def get_prospection_status():
    """Rapport d'état complet de la prospection, règles, tunnels et sources."""
    init_db()
    cibles = lire_catalogue()
    tunnels = verifier_tunnels()
    regles, _ = charger_regles_prospection()
    
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    cur = conn.cursor()
    
    cur.execute("SELECT count(*) FROM contacts_moissonnes;")
    total_contacts = cur.fetchone()[0]
    
    cur.execute("SELECT COALESCE(pole, 'non_classe'), count(*) FROM contacts_moissonnes GROUP BY pole ORDER BY count(*) DESC;")
    contacts_par_pole = {row[0]: row[1] for row in cur.fetchall()}
    
    cur.execute("SELECT COALESCE(segment, 'non_route'), count(*) FROM contacts_moissonnes GROUP BY segment ORDER BY count(*) DESC;")
    contacts_par_segment = {row[0]: row[1] for row in cur.fetchall()}
    
    cur.execute("""
        SELECT entreprise, pole, email, url_source, moissonne_le,
               COALESCE(segment, 'non_route'), COALESCE(processus_qui_saigne, '')
        FROM contacts_moissonnes
        ORDER BY id DESC
        LIMIT 15;
    """)
    derniers_contacts = [
        {
            "entreprise": r[0], "pole": r[1], "email": r[2], "url_source": r[3],
            "date": r[4], "segment": r[5], "processus_qui_saigne": r[6]
        }
        for r in cur.fetchall()
    ]
    
    conn.close()
    
    cibles_par_pole = {}
    for c in cibles:
        p = c["pole"]
        cibles_par_pole[p] = cibles_par_pole.get(p, 0) + 1

    return {
        "success": True,
        "timestamp": datetime.now().isoformat(),
        "total_contacts": total_contacts,
        "total_cibles": len(cibles),
        "total_regles": len(regles),
        "contacts_par_pole": contacts_par_pole,
        "contacts_par_segment": contacts_par_segment,
        "cibles_par_pole": cibles_par_pole,
        "tunnels": tunnels,
        "derniers_contacts": derniers_contacts
    }


def rechercher_entreprises_gouv(query: str, departement: str = "31", code_naf: str = None, limite: int = 10):
    """
    Interroge l'API Open-Data officielle du gouvernement français
    (Recherche Entreprises / SIRENE / INPI) pour extraire les entités légales,
    dirigeants et adresses avec zéro token.
    """
    params = {
        "q": query,
        "per_page": min(limite, 25)
    }
    if departement:
        params["departement"] = departement
    if code_naf:
        params["activite_principale"] = code_naf
        
    url = f"{URL_API_GOUV}?{urllib.parse.urlencode(params)}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "JarvisCockpitOpenData/1.0"})
        with urllib.request.urlopen(req, timeout=5.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            resultats = []
            for item in data.get("results", []):
                dirigeants = []
                for d in item.get("dirigeants", []):
                    nom = f"{d.get('prenoms', '')} {d.get('nom', '')}".strip()
                    qualite = d.get("qualite", "")
                    if nom:
                        dirigeants.append(f"{nom} ({qualite})" if qualite else nom)
                        
                siege = item.get("siege", {})
                adresse = siege.get("adresse", "")
                nom_complet = item.get("nom_complet", "")
                activite = item.get("activite_principale", "")
                
                # Auto-qualification déterministe
                qualif = qualifier_prospect(
                    f"{nom_complet} {activite}",
                    {"siren": item.get("siren", ""), "dirigeant": ", ".join(dirigeants)}
                )
                
                resultats.append({
                    "nom_complet": nom_complet,
                    "siren": item.get("siren", ""),
                    "activite_principale": activite,
                    "adresse": adresse,
                    "code_postal": siege.get("code_postal", ""),
                    "ville": siege.get("commune", ""),
                    "dirigeants": dirigeants[:3],
                    "etat_administratif": item.get("etat_administratif", "A"),
                    "segment_qualifie": qualif["segment"],
                    "processus_qui_saigne": qualif["processus_qui_saigne"],
                    "score": qualif["score"]
                })
            return {"success": True, "count": len(resultats), "entreprises": resultats}
    except Exception as e:
        return {"success": False, "error": str(e), "entreprises": []}


def fetch_url(url: str, timeout: int = 12):
    """Télécharge une URL publique en simulant un navigateur standard."""
    try:
        r = subprocess.run(
            ["curl", "-sSL", "-m", str(timeout), "--compressed",
             "-A", "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0",
             "-w", "\n__H__%{http_code}", url],
            capture_output=True, text=True, timeout=timeout + 4, errors="replace"
        )
        out = r.stdout
        code = 0
        if "__H__" in out:
            out, _, tail = out.rpartition("__H__")
            code = int(tail.strip() or 0)
        return out, code
    except Exception:
        return "", 0


def moissonner_cible(cible: dict, timeout: int = 10):
    """
    Scanne les pages publiques d'une cible (0 token, curl + regex déterministe)
    et enregistre les contacts avec leur qualification selon les règles de Rémi.
    """
    init_db()
    nom = cible["nom"]
    pole = cible["pole"]
    base_url = cible["url"].rstrip("/")
    
    qualif = qualifier_prospect(f"{nom} {pole}", {"url": base_url})
    segment = qualif["segment"]
    saigne = qualif["processus_qui_saigne"]
    score = qualif["score"]
    
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    nouveaux_contacts = []
    vus = set()
    now_str = datetime.now().isoformat(timespec="seconds")
    
    for path in CHEMINS_MOISSON:
        full_url = base_url + path
        html, code = fetch_url(full_url, timeout=timeout)
        mails = set()
        if code == 200 and html:
            for m in RE_MAIL.findall(html):
                m = m.strip(".,;:'\"()<>").lower()
                if BRUIT.search(m) or len(m) > 64:
                    continue
                mails.add(m)
                
        for m in mails:
            if m not in vus:
                vus.add(m)
                try:
                    cur.execute("""
                        INSERT OR IGNORE INTO contacts_moissonnes
                        (entreprise, pole, email, formulaire_url, url_source, moissonne_le,
                         segment, processus_qui_saigne, score)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """, (nom, pole, m, "", full_url, now_str, segment, saigne, score))
                    if cur.rowcount > 0:
                        nouveaux_contacts.append(m)
                except Exception:
                    pass
                    
        cur.execute("""
            INSERT INTO moisson_journal (entreprise, url, http, mails, horodatage)
            VALUES (?, ?, ?, ?, ?);
        """, (nom, full_url, code, len(mails), now_str))
        
    conn.commit()
    conn.close()
    
    return {
        "entreprise": nom,
        "pole": pole,
        "segment": segment,
        "processus_qui_saigne": saigne,
        "score": score,
        "pages_scannees": len(CHEMINS_MOISSON),
        "nouveaux_contacts": len(nouveaux_contacts),
        "emails": nouveaux_contacts
    }


def generer_message_prospection(prospect: dict, style: str = "accroche") -> dict:
    """
    Génère un message d'approche B2B percutant, respectueux et non-intrusif
    en s'appuyant sur le 'processus qui saigne' qualifié.
    Supporte 3 styles :
      - 'accroche' : premier contact (< 80 mots), 1 question concrète sur le processus qui saigne
      - 'relance'  : relance polie à J+3 sans pression avec retour d'expérience
      - 'linkedin' : InMail direct et concis (< 45 mots)
    Utilise exclusivement les moteurs locaux (LM Studio ou Rémi via tunnel). 0 token cloud.
    """
    nom = prospect.get("entreprise") or prospect.get("nom") or "Madame, Monsieur"
    segment = prospect.get("segment") or "Entreprise"
    saigne = prospect.get("processus_qui_saigne") or "l'automatisation de vos flux récurrents"
    dirigeant = prospect.get("dirigeant") or ""
    
    if style == "relance":
        prompt = f"""Tu es Franck, fondateur d'une solution d'IA souveraine locale à Toulouse (JARVIS).
Rédige un email de relance doux et poli (J+3) sans pression pour :
- Entreprise : {nom}
- Interlocuteur : {dirigeant or 'Direction'}
- Sujet : {saigne}
Contraintes : 3 phrases maximum, moins de 60 mots. Demande simplement si le sujet fait écho à leurs priorités actuelles."""
    elif style == "linkedin":
        prompt = f"""Tu es Franck (JARVIS Toulouse, IA souveraine on-premise).
Rédige un message LinkedIn / InMail direct et ultra-court pour :
- Entreprise : {nom}
- Interlocuteur : {dirigeant or 'Bonjour'}
- Sujet : {saigne}
Contraintes : 2 à 3 phrases maximum, moins de 45 mots. Zéro formule pompeuse."""
    else:
        prompt = f"""Tu es Franck, fondateur d'une solution d'automatisation et d'IA souveraine locale à Toulouse (JARVIS).
Rédige un message d'approche B2B direct, humble, professionnel et sans jargon marketing pour cette entreprise :
- Entreprise : {nom}
- Interlocuteur : {dirigeant or 'Direction'}
- Segment : {segment}
- Problème précis visé (le processus qui saigne) : {saigne}

Contraintes strictes :
1. Maximum 4 phrases. Moins de 80 mots.
2. Pose une question directe et concrète sur {saigne}.
3. Propose un simple échange technique de 10 minutes ou une démo locale sur machine dédiée sans engagement.
4. Zéro flatterie, zéro promesse magique, ton franc et technique."""

    # 1. Essai LM Studio local (:1234)
    payload = {
        "model": "qwen3-8b",
        "messages": [
            {"role": "system", "content": "Tu rédiges des messages B2B courts, factuels et percutants en français."},
            {"role": "user", "content": f"/nothink\n{prompt}"}
        ],
        "temperature": 0.3,
        "max_tokens": 250
    }
    
    try:
        req = urllib.request.Request(
            f"{LOCAL_LMSTUDIO_URL}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=15.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            content = data["choices"][0]["message"]["content"].strip()
            content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
            return {"success": True, "engine": "LM Studio Local (qwen3-8b · 48.4 tok/s)", "style": style, "message": content}
    except Exception:
        pass

    # 2. Repli vers Ollama Rémi via tunnel (:11500)
    try:
        payload_ollama = {
            "model": "qwen3:1.7b",
            "prompt": prompt,
            "stream": False
        }
        req = urllib.request.Request(
            f"{REMI_OLLAMA_URL}/api/generate",
            data=json.dumps(payload_ollama).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=15.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            content = data.get("response", "").strip()
            return {"success": True, "engine": "Ollama Rémi (:11500)", "style": style, "message": content}
    except Exception as e:
        # 3. Modèle déterministe de secours si aucun LLM actif
        salut = f"Bonjour {dirigeant.split('(')[0].strip()}," if dirigeant else "Bonjour,"
        modele_secours = (
            f"{salut}\n\n"
            f"J'ai remarqué le développement de {nom} dans votre secteur. "
            f"Chez plusieurs confrères, le point de friction majeur reste souvent {saigne}.\n\n"
            f"Nous avons développé un socle souverain (100% hébergé en local, zéro fuite cloud) "
            f"qui automatise précisément ce type de chaîne.\n\n"
            f"Seriez-vous ouvert à un retour d'expérience direct de 10 minutes cette semaine ?\n\n"
            f"Bien cordialement,\nFranck — JARVIS Toulouse"
        )
        return {"success": True, "engine": "Modèle Déterministe Secours", "style": style, "message": modele_secours, "note": str(e)}


def router_batch_donnees(lignes: list[dict]) -> dict:
    """
    Routage déterministe par lot (CSV / JSON), inspiré du route-batch de Rémi.
    Traite chaque entrée, calcule le segment, le score et l'action recommandée.
    """
    resultats = []
    stats_segments = {}
    
    for l in lignes:
        ent = l.get("entreprise") or l.get("nom") or l.get("company") or "Inconnu"
        ville = l.get("ville") or l.get("city") or ""
        pole = l.get("pole") or l.get("secteur") or ""
        dirigeant = l.get("dirigeant") or l.get("contact") or ""
        site = l.get("site_web") or l.get("url") or l.get("website") or ""
        
        texte = f"{ent} {ville} {pole} {site}".strip()
        qualif = qualifier_prospect(texte, {"dirigeant": dirigeant, "url": site, "nom": ent})
        
        seg = qualif["segment"]
        stats_segments[seg] = stats_segments.get(seg, 0) + 1
        
        resultats.append({
            "entreprise": ent,
            "ville": ville,
            "pole": pole,
            "dirigeant": dirigeant,
            "site_web": site,
            "segment": seg,
            "score": qualif["score"],
            "processus_qui_saigne": qualif["processus_qui_saigne"],
            "priorite": qualif.get("priorite", "🌱 VEILLE"),
            "action_recommandee": qualif.get("action_recommandee", ""),
            "occurrences": qualif.get("occurrences", [])
        })
        
    return {
        "success": True,
        "total": len(lignes),
        "segments": stats_segments,
        "cibles": sorted(resultats, key=lambda x: x["score"], reverse=True)
    }

