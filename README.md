# JARVIS Cockpit — application de bureau

Application de pilotage JARVIS : **15 onglets** PyQt6 natifs, plus un serveur
HTTP local (`:8600`) qui expose les mêmes données en JSON et sert une interface
web équivalente.

Une seule base de code, **trois formes d'exécution** — toutes vérifiées en
lançant réellement l'application, pas en supposant qu'elle démarre.

| Forme | Lancement | Empreinte |
|---|---|---|
| Installée | `bin/jarvis-cockpit-app` | — |
| Disque virtuel VHDX | `bin/jarvis-cockpit-vhdx lancer` | 100 Mo réels (2 Go annoncés) |
| Portable USB | `portable/JARVIS-COCKPIT.sh` | 980 Ko |

## Les 15 onglets

Cockpit Exécutif · Avancements & Sync · Claude Code Suite · Applications Bureau
· Terminal & TMUX · Table Ronde & Experts · Board Plan & To-Do · Bases SQL
· Studio Création IA · Serveurs MCP · Swarm & Services · Cluster & Matériel
· Moissonnage & Vente · Hub IA Web / CDP / Notion · Bureau GNOME & Verrous

## Prérequis

Python 3 et PyQt6 :

```bash
sudo apt install python3-pyqt6
```

PyQt6 n'est **pas** embarqué dans la version portable : ~100 Mo, et il dépend
des bibliothèques graphiques de la machine hôte. Sans lui, `--web` donne le
même cockpit dans un navigateur — le serveur n'a besoin que de la bibliothèque
standard.

## Comment la portabilité est obtenue

Le lanceur portable déduit sa racine de **sa propre position**
(`readlink -f "$0"`), puis pose `JARVIS_COCKPIT_ROOT`. Toute l'application lit
ses chemins depuis là, et écrit ses données à côté du lanceur — jamais dans le
home de la machine hôte.

`JARVIS_COCKPIT_ROOT` est une variable **dédiée**, distincte de `JARVIS_HOME`
que `~/.profile` exporte déjà : les confondre activait le mode portable en
permanence, y compris sur la machine d'origine.

## Routes du serveur

`/api/status` · `/api/bureau/etat` · `/api/apps/all` · `/api/databases`
· `/api/postgres` · `/api/tailscale` · `/api/peripheriques` · `/api/inventaire`
· `/api/mcps` · `/api/swarm` · `/api/tasks` · `/api/board/stats`
· `/api/term/*` (terminaux tmux) · `/api/claude` · `/api/cdp/status`

## Deux pièges rencontrés, et traités dans le code

**Sous `/media/<user>/`, tout n'est pas un support.** De vrais points de
montage y côtoient de simples répertoires du disque système : un `df` sur ces
derniers retombe silencieusement sur `/` et annonce l'espace de la racine.
`jarvis-cockpit-exporter` affiche le périphérique de chaque entrée et **refuse**
d'exporter vers une cible qui retombe sur la racine.

**Un service `systemd --user` n'hérite pas de l'environnement graphique.** Il
ne reçoit ni `XDG_SESSION_TYPE` ni `XDG_CURRENT_DESKTOP` : lire `os.environ`
rendait `"?"` et `wayland=false` sur une session bel et bien Wayland. La
détection passe par `loginctl`, qui interroge logind et ne dépend pas de
l'environnement du processus.

## Ce que le dépôt ne contient pas

Aucun secret, aucune base de données, aucun journal. Les profils shell de la
machine d'origine sont exclus : `~/.bashrc` y porte un jeton en clair.
