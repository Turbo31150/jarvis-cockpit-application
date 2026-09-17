# Journal des Modifications (CHANGELOG) — Turbo OS / Cockpit Unifié

Toutes les modifications notables apportées à ce projet sont documentées dans ce fichier.
Le format est basé sur [Keep a Changelog](https://keepachangelog.com/fr/1.0.0/).

## [2.0.0-turbo-os-unification] - 2026-09-17

### Restructuration & Consolidation Majeure (Master Directive)

#### Ajouté (Added)
- **Registres Cœur Unifiés** (`cockpit/core/`) :
  - `model_registry.py` : Télémétrie et probing réel des modèles d'inférence GPU (GPU0: qwen2.5-7b :1234, GPU1: qwen3-8b :1235, Embed: nomic :1300).
  - `stub_registry.py` : Cartographie formelle des endpoints du cockpit, conversion des faux `success:true` en statuts transparents (501 Not Implemented explicites).
  - `database_registry.py` : Accès et intégrité centralisés aux bases vivantes SQLite (`jarvis.db`, `board.db`, `jarvis_master.db`, etc.).
  - `dispatcher.py` : `TurboDispatcher` et boucle d'exécution unifiée avec coupe-circuit (`MAX_TOOL_LOOPS=10`) et garde-fous de timeout.
  - `voice_lock.py` : Verrou d'exclusion mutuelle évitant les collisions de synthèse vocale et d'écoute STT.
- **Packaging Autonome (C17/C18)** :
  - `bin/jarvis-planning-widget.py` : Intégration canonique du widget planning (:8899) avec tolérance d'arguments CLI.
  - `bin/jarvis-cockpit.sh` : Wrapper canonique d'exécution redirigeant vers `jarvis-cockpit-app`.
  - `bin/swarm-watch.sh` : Superviseur Docker Swarm / microservices autonome avec mode `--once`.
  - `bin/m6-watch.sh` : Superviseur réseau et GPU du cluster M6 (10.42.0.230) avec mode `--once`.
  - `scripts/planning_mega_m4.py` : Générateur canonique de la file de tâches unifiée (`jarvis_master.db`).
  - Tolérance dynamique de chemin dans `bin/jarvis-cockpit-vhdx` et `bin/jarvis-cockpit-exporter` avec repli automatique vers `~/jarvis/data` lorsque `/data` est absent.
- **Batterie de Tests Globale** :
  - `cockpit/tests/test_suite_turbo_os.py` : Suite automatisée de 14 tests de non-régression couvrant santé cockpit, inférence GPU, STT, TTS, MCP, RAG, Domino, sécurité et packaging.

#### Sécurité (Security)
- **C-SEC P0** : Activation du filtre `local_seulement()` sur le serveur Cockpit (`:8600`).
  - Rejet systématique (HTTP 403 Forbidden) des requêtes distantes non authentifiées.
  - Autorisation par jeton Bearer (`Authorization: Bearer <secret>`).
  - Passage fluide et sans friction du trafic local loopback (`127.0.0.1`).

#### Corrigé (Fixed)
- **Scraping Sirene** : Correction de `/api/scraping/recherche_gouv` préservant les paramètres query-string (`q`, `dep`).
- **Chantiers** : Renvoi explicite de 501 Not Implemented sur `/api/chantiers/action` en l'absence physique des binaires de production, éliminant tout faux succès silencieux.
- **Voix / Audio** : Élimination de la double parole vocale concurrente dans l'UI cognitive OMEGA au profit d'une voix unique d'arbitrage.
- **Archivage des Doublons (C16)** : Isolation et archivage des 6 copies divergentes et obsolètes de `serveur.py` vers l'armoire de sauvegarde `legacy_serveur_copies/` avec `README_MIGRATED.txt`.
- **CLI & Packaging Robuste (C17/C18)** :
  - Prise en charge standard de `-h` et `--help` sur tous les outils (`install-cockpit.sh`, `planning_mega_m4.py`, `m6-watch.sh`, `swarm-watch.sh`).
  - Éradication du bogue d'insertion involontaire de tâches dans `jarvis_master.db` lors d'un appel d'aide sur `scripts/planning_mega_m4.py`.
  - Élimination des blocages en boucle infinie sur `bin/m6-watch.sh` et `bin/swarm-watch.sh` lors du passage d'arguments non numériques.
  - Enrichissement de `install-cockpit.sh` pour garantir la copie de `cockpit/terminaux.py`, `cockpit/launch_gui.sh`, des scripts tmux/vecto et de tous les fichiers web (`turbo.html`, `vendor/`), validé sur environnement hôte vierge isolé.
  - Nettoyage des 6 fichiers résiduels de 0 octet (`--help`, `-help`, etc.) dans `cockpit/`.
