#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
serveur.py (racine du dépôt) — POINT D'ENTRÉE DE COMPATIBILITÉ
===============================================================
Ce fichier était une COPIE PÉRIMÉE de cockpit/serveur.py (sans /api/legion,
/api/remodelage, type MIME .md) qui, lancée depuis la racine, ne trouvait ni
core/ ni terminaux.py (ModuleNotFoundError sur toutes les plateformes).

Il exécute désormais le vrai serveur cockpit/serveur.py (une seule source de
vérité), avec les mêmes variables d'environnement (COCKPIT_PORT, COCKPIT_BIND).

Usage :  python serveur.py        (équivalent à  python cockpit/serveur.py)
"""

import os
import runpy
import sys

RACINE = os.path.dirname(os.path.abspath(__file__))
SERVEUR_COCKPIT = os.path.join(RACINE, "cockpit", "serveur.py")


def main():
    if not os.path.isfile(SERVEUR_COCKPIT):
        sys.stderr.write(f"serveur.py : introuvable — {SERVEUR_COCKPIT}\n")
        sys.exit(1)
    # cockpit/ en tête du sys.path, comme si on lançait cockpit/serveur.py directement
    cockpit_dir = os.path.dirname(SERVEUR_COCKPIT)
    if cockpit_dir not in sys.path:
        sys.path.insert(0, cockpit_dir)
    runpy.run_path(SERVEUR_COCKPIT, run_name="__main__")


if __name__ == "__main__":
    main()
