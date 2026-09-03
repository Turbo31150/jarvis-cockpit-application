# JARVIS MASTER COCKPIT

Application de pilotage du parc JARVIS. **Zéro dépendance** : bibliothèque
standard `python3` uniquement — aucun `pip install`, aucun paquet système.

## Les trois façades

| Façade | Port | Fichier | Rôle |
|---|---|---|---|
| **Cockpit PWA** | `8600` | `cockpit/serveur.py` | pilotage à distance depuis le navigateur ou le téléphone (installable en PWA : `web/manifest.json` + `web/sw.js`), STT/TTS français locaux, lancement des applis, sondes M6 / S8 |
| **Widget planning** | `8899` | `bin/jarvis-planning-widget.py` | « ce que le système fait vraiment » : timers systemd, file de tâches (`tasks`), tâches faites, ~16 cartes, rafraîchi toutes les 5 s (cache TTL 3 s) |
| **Multiplexeur TTX** | tmux | `bin/ttx` | cockpit terminal 14 fenêtres (Claude, table ronde, planning, swarm, OpenClaw, Oméga, Manus, Mistral, web/CDP, Gemini, Antigravity, widget, M6) |

## Installation sur une machine du parc

```bash
git clone https://github.com/Turbo31150/jarvis-m4-core.git ~/jarvis-cockpit
~/jarvis-cockpit/cockpit/install-cockpit.sh
```

L'installateur est **idempotent** et **non destructif** : il sauvegarde tout
fichier qu'il remplace (`.bak-AAAAMMJJ-HHMMSS`), ne touche à aucun dépôt git
existant, et ne réinitialise jamais une base déjà présente.

Options :

```bash
./install-cockpit.sh --sans-service                 # pas de systemd, lancement manuel
./install-cockpit.sh --port-widget 9899 --port-cockpit 8601
```

Ce qu'il fait, dans l'ordre : prérequis → arborescence `~/jarvis/{bin,logs,data,cockpit}`
→ pose des fichiers → création de `jarvis_master.db` (tables `tasks` + `plan` +
index) si absente → units systemd `--user` + `enable --now` + `linger`
→ **vérification HTTP réelle des deux ports** avant de rendre la main.

## Mode dégradé — ce qui est normal sur une machine autre que M4

Les cartes se dégradent proprement, elles ne cassent pas la page :

- pas de GPU NVIDIA → carte GPU vide ;
- pas de nœud M6 (`10.42.0.230:1234`) → carte M6 muette ;
- pas de `board.db` → carte bibliothèque à zéro ;
- pas de Docker Swarm → carte infra vide.

`bin/ttx` suppose en revanche la présence de `claude`, `gemini`, `openclaw`,
`nvidia-smi` : sur une machine qui ne les a pas, les fenêtres concernées
s'ouvrent sur un shell, sans erreur bloquante.

## Désinstallation

```bash
systemctl --user disable --now jarvis-planning-widget jarvis-cockpit
rm -f ~/.config/systemd/user/jarvis-{planning-widget,cockpit}.service
systemctl --user daemon-reload
```

Les données (`~/jarvis/jarvis_master.db`, `~/jarvis/logs`) sont conservées.
