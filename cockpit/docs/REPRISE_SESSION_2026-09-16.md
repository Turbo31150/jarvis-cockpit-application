# Point de reprise — portage Windows JARVIS Cockpit — 2026-09-16

> Sauvegardé sur 4 supports : ce fichier (GitHub, branche `portage-windows`), SQLite
> (`jarvis_master.db.cockpit_settings`, `jarvis_logs.db.bureau_actions`,
> `jarvis_action_memory.db.action_memory`), Postgres rig `mining`
> (`jarvis.session_artifacts`, clé `session::2026-09-16::cockpit-windows-reprise`),
> mémoire Claude Code (`jarvis-cockpit-windows-port`).

## 1. Où on en est

| Élément | État |
|---|---|
| Dépôt | `C:\Users\clair\jarvis-cockpit-application` (= `/mnt/c/...` sous WSL), remote `Turbo31150/jarvis-cockpit-application`, base `main@96e143f` |
| Portage Windows | **entièrement non committé jusqu'à ce point** → commit WIP sur branche `portage-windows` |
| Venv | `.venv` (Python 3.13.7, PyQt6, textual, psutil, requests) |
| Symptôme réparé | « rien ne s'ouvre, les terminaux » = `Popen(["gnome-terminal", …])` en dur → `FileNotFoundError [WinError 2]` (log `C:\Users\clair\jarvis\logs\cockpit_gui.log`) |
| Corrigé (session du 16/09) | `tab_iaweb.py`, `tab_swarm.py`, `tab_moisson.py` routés par `platform_compat.open_terminal()` + boutons grisés si cible absente ; `agy` retiré de `LINUX_ONLY_TOOLS` + chemin `%LOCALAPPDATA%\agy\bin\agy.exe` ; candidats `browseros` |
| Validation | `tests_platform_compat` 54 OK (Python Windows) ; smoke PyQt6 offscreen des 3 onglets OK |
| Déjà porté avant | `tab_hud`, `tab_apps`, `tab_terminal`, `terminal_manager`, `claude_engine`, `apps_registry`, `platform_compat` |

## 2. Audit exhaustif — ARRÊTÉ à 30/48 fichiers (sur demande, pour reprise au démarrage)

- Résultats bruts figés dans **`cockpit/docs/audit_windows_2026-09-16_brut.json`** (36 trouvailles, 5 bloquantes, 0 vérifiée).
- **18 fichiers restent à auditer** : core/table_ronde_engine.py, core/notion_engine.py, core/mcp_registry.py, core/prospection_engine.py, core/settings_engine.py, core/telemetry.py, core/config.py, core/database.py, core/content_engine.py, core/inference.py, core/action_memory.py, core/twilio_orchestrator.py, gui_app.py, app.py, terminaux.py, serveur.py, ui/theme.py, ../jarvis_cockpit_launcher.pyw
- Le journal JSONL d'origine reste lisible tant que la session Claude Code existe (chemins ci-dessous), mais le JSON ci-dessus suffit.

- Run ID `wf_c9ae017a-791` — script
  `~/.claude/projects/-home-turbo/64b2fd79-cb2b-46c8-a9cc-381755cc32ae/workflows/scripts/audit-cockpit-windows-wf_c9ae017a-791.js`
- Journal des résultats (lisible à la main, JSONL) :
  `~/.claude/projects/-home-turbo/64b2fd79-cb2b-46c8-a9cc-381755cc32ae/subagents/workflows/wf_c9ae017a-791/journal.jsonl`
- Structure : 48 auditeurs (1/fichier) → 3 vérificateurs adversariaux par trouvaille (échec réel / atteignable / déjà protégé, confirmé si ≥ 2 votes) → critique de complétude par grep global → re-vérification.
- ⚠ Le workflow **ne survit pas à la fin de la session Claude Code** (resume = même session). Si perdu : relire `journal.jsonl` (entrées `type=result` avec `findings`) et relancer le script.

### Trouvailles brutes à 30/48 fichiers (non encore vérifiées)

Bloquantes probables :
- `ui/tabs/tab_plan.py:22` — `subprocess.run(["python3", f"{JARVIS_DIR}/scripts/planning_mega_m4.py"…` → `python3` = alias Store + script absent sous Windows
- `ui/tabs/tab_omega.py:39` — `subprocess.run(["python3", script_path…` (omega/engine) → idem
- `core/escouade_engine.py:17` — `MASTER_DB = "/home/turbo/jarvis/jarvis_master.db"` en dur
- `core/jarvis_core_loop.py:64` — `subprocess.run(["bash", "-lc", cmd]…` (bash = lanceur WSL sous Windows)
- `core/sync_engine.py:318` — `git -C JARVIS_DIR add -A / commit` : JARVIS_DIR n'est pas un dépôt git sous Windows

Dégradées (à trier) : `tab_avancements` (sync/timers systemd), `tab_claude:58`, `tab_moisson:79` (script absent → message), `tab_omega` (sys.path omega), `tab_table_ronde:452`, `apps_registry:360/376`, `escouade_engine:163/196` (points de montage SSD Linux), `inventaire:65`, `jarvis_core_loop` (dispatcher/tts/tmp), `sync_engine:37/47/97`.

Fichiers audités propres : `tab_apps`, `tab_bureau`, `tab_cluster`, `tab_hud`, `tab_mcps`, `tab_settings`, `tab_sql`, `tab_studio`, `tab_swarm`, `tab_terminal` (+ autres sans trouvaille).

## 3. Prochaines étapes (dans l'ordre)

1. Au redémarrage : relancer l'audit sur les fichiers restants, puis **vérifier** les 36 trouvailles du JSON (3 lentilles : échec réel / atteignable / déjà protégé) → liste confirmée.
2. Corriger chaque site confirmé **sans toucher au chemin Linux** : branche `IS_WINDOWS` ou routage via `platform_compat` (`open_terminal`, `safe_popen`, `python_executable()`, `jarvis_path(..., must_exist=True)`, `no_window_kwargs()`, `unavailable_message()`), bouton grisé + infobulle si cible absente.
3. Re-valider : `tests_platform_compat` (54) + smoke offscreen de **tous** les onglets + lancement réel `JARVIS-Cockpit.cmd`.
4. Commit sur `portage-windows`, puis PR vers `main` quand le rig Linux a été re-testé (`bin/*`, `install.sh` inchangés).

## 4. Comment relancer les outils depuis WSL

- Python Windows : écrire un `.cmd` dans `C:\Users\clair\AppData\Local\Temp\` (`set "PYTHONUTF8=1"`, `set "PYTHONPATH=…\cockpit"`, `.venv\Scripts\python.exe …`) et l'appeler via `cmd.exe /c` — un `set` inline dans `cmd.exe /c '…'` casse (`invalid PYTHONUTF8`).
- Tests : `.venv\Scripts\python.exe -m unittest tests_platform_compat -q` (cwd = racine, PYTHONPATH = cockpit).
- Smoke PyQt6 : `QT_QPA_PLATFORM=offscreen`, instancier les `Tab*` et lister `findChildren(QPushButton)` (enabled + toolTip).
- Git : utiliser le **git Windows** (`core.autocrlf=true`) pour add/commit/push — le git WSL voit 52 fichiers « modifiés » qui ne sont que du CRLF de checkout. `gh.exe` est authentifié (`Turbo31150`, scopes repo).
- Postgres rig : `ssh turbo@10.42.0.1 docker exec -i jarvis-postgres psql -U jarvis -d jarvis` (5432 lié à 127.0.0.1 du rig uniquement).

## 5. Poste Windows (faits vérifiés)

Présents : `wt.exe`, `claude.cmd` (npm) + `~\.local\bin\claude.exe`, `ollama.exe`, `docker.exe`, `agy.exe` (`%LOCALAPPDATA%\agy\bin`), Git for Windows, `gh.exe`, Python 3.11 + 3.13.
Absents : Claude Desktop, BrowserOS, tmux, gnome-terminal, `C:\Users\clair\jarvis\scripts\`, `…\bin\`, Postgres local.
`JARVIS_DIR = C:\Users\clair\jarvis` (logs/, data/, databases/, board/, cockpit/, `jarvis_master.db`).

## 6. Hors périmètre, en attente de consigne

- `C:\Users\clair\Downloads\MEGA_PROMPT_OMEGA_CANONIQUE.md` (1 387 lignes, prompt « architecture cognitive JARVIS Ombre/Lumière ») — non traité.
- Dépôts `pamerys-m4-full`, `projet-1`, `jarvis-board-multi-ia` : déjà clonés dans `C:\Users\clair`, rien fait dessus.
