# JARVIS Cockpit sous Windows

Ce document décrit l'installation et l'usage de JARVIS Cockpit comme **vraie
application de bureau Windows** (raccourci, icône, aucune console), sur un PC
Windows 11 avec Python 3.11+ installé. Les scripts Linux (`install.sh`,
`portable/JARVIS-COCKPIT.sh`, `bin/*`) restent la voie normale sur le rig Linux :
rien n'a changé pour lui.

## Prérequis

| Composant | Où / comment |
|-----------|--------------|
| Python 3.13 (ou 3.11) | `C:\Python313\python.exe` — sinon `py -3` (python.org, pas la version Microsoft Store) |
| Git for Windows | optionnel, pour `git pull` |
| LM Studio | `C:\Program Files\LM Studio`, serveur local sur `http://127.0.0.1:1234` |
| Ollama | `%LOCALAPPDATA%\Programs\Ollama`, serveur sur `http://127.0.0.1:11434` |
| Windows Terminal (`wt.exe`) | optionnel, utilisé pour le mode `--tui` (sinon `cmd.exe`) |
| NVIDIA `nvidia-smi.exe` | `C:\Windows\System32\nvidia-smi.exe` (télémétrie VRAM) |

Aucun droit administrateur n'est nécessaire.

## Installation

Depuis la racine du dépôt (PowerShell) :

```powershell
cd C:\Users\clair\jarvis-cockpit-application
powershell -ExecutionPolicy Bypass -File install.ps1
```

Le script est **idempotent** (relançable à volonté). Il :

1. choisit le meilleur Python (`C:\Python313`, puis `C:\Python311`, puis `py -3`) ;
2. crée ou met à jour `.venv\` et installe `requirements.txt`
   (PyQt6, textual, psutil, requests) ;
3. crée le dossier de données `%USERPROFILE%\jarvis\{logs,data,databases,board,cockpit}` ;
4. fabrique `icons\jarvis_cockpit.ico` s'il manque (`icons\make_ico.py`, sans dépendance
   supplémentaire : redimensionnement PyQt6 + conteneur ICO écrit en pur Python) ;
5. crée les raccourcis, avec l'icône et le dossier de travail = racine du dépôt :
   - Bureau : **JARVIS Cockpit** (application PyQt6, via `pythonw.exe`, sans console)
   - Menu Démarrer › Programmes › **JARVIS Cockpit** :
     - *JARVIS Cockpit* — application de bureau
     - *JARVIS Cockpit Web (port 8600)* — serveur HTTP local
     - *JARVIS Cockpit TUI* — tableau de bord Textual en console
     - *JARVIS Cockpit (console de débogage)* — même appli, console visible

Options : `-SansRaccourcis` (pas de .lnk), `-Reinstaller` (recrée `.venv`),
`-SansPip` (hors ligne). **Aucune modification du registre ni du PATH.**

Pour désinstaller : supprimer les raccourcis, le dossier `.venv\` et, si vous
voulez effacer vos données, `%USERPROFILE%\jarvis\`.

## Lancement

| Mode | Raccourci | Ligne de commande |
|------|-----------|-------------------|
| Application de bureau (15 onglets) | Bureau / menu Démarrer | `JARVIS-Cockpit.cmd` |
| Serveur web `:8600` | menu Démarrer › Web | `JARVIS-Cockpit.cmd --web` puis <http://127.0.0.1:8600> |
| Tableau de bord TUI | menu Démarrer › TUI | `JARVIS-Cockpit.cmd --tui` |

Les raccourcis pointent sur `jarvis_cockpit_launcher.pyw`, qui :

- pose `JARVIS_HOME=%USERPROFILE%\jarvis` si la variable est absente ;
- se place dans la racine du dépôt et ajoute `cockpit\` au `sys.path` ;
- redirige `stdout`/`stderr` vers le journal (indispensable sous `pythonw.exe`,
  qui n'a pas de console) ;
- installe un `sys.excepthook` : en cas de plantage, une **boîte de dialogue**
  affiche la trace et le chemin du journal. Un échec est donc visible, jamais
  une fermeture silencieuse.

`JARVIS-Cockpit.cmd` fait la même chose avec une console visible et **reste
ouvert** (`pause`) si le programme se termine en erreur : c'est l'outil de
diagnostic à utiliser en premier.

L'application n'accepte qu'une seule instance : relancer le raccourci ramène
la fenêtre existante au premier plan.

## Où vivent les données et les journaux

| Quoi | Chemin |
|------|--------|
| Dossier de données (`JARVIS_HOME`) | `C:\Users\clair\jarvis\` |
| Journal du lanceur / plantages | `C:\Users\clair\jarvis\logs\cockpit-gui.log` (rotation à 2 Mo → `.log.1`) |
| Bases SQLite | `C:\Users\clair\jarvis\jarvis_master.db`, `board\board.db`, `data\*.db`, `logs\jarvis_logs.db` |
| Environnement Python | `<dépôt>\.venv\` (ignoré par git) |
| Fichier `.env` (clés API) | `%USERPROFILE%\jarvis\.env` ou `%USERPROFILE%\.env` (`CLE=valeur`, une par ligne) |

Pour déplacer les données : définir `JARVIS_HOME` (variable utilisateur
Windows, ou `set JARVIS_HOME=D:\jarvis` avant `JARVIS-Cockpit.cmd`) et relancer
`install.ps1` pour que les sous-dossiers existent.

## Pointer l'application vers LM Studio / Ollama de ce PC

Par défaut la configuration (`cockpit\core\config.py`) vise le réseau du rig
Linux (LM Studio sur `192.168.42.241`, nœuds Tailscale de Rémi, etc.). Sur ce
PC, tout tourne en local : posez les variables d'environnement ci-dessous
(variables utilisateur Windows via *Paramètres › Système › Variables
d'environnement*, ou dans `%USERPROFILE%\jarvis\.env`, lu au démarrage) :

```ini
JARVIS_LMSTUDIO_HOST=127.0.0.1
JARVIS_LMSTUDIO_PORT=1234
# Optionnel : URL complète si LM Studio écoute ailleurs
# JARVIS_LMSTUDIO_URL=http://127.0.0.1:1234
# M6 = alias historique du serveur LM Studio ; suit LMSTUDIO_* si absent
# JARVIS_M6_HOST=127.0.0.1
# JARVIS_M6_PORT=1234
# 2e machine GPU (Ollama exposé en OLLAMA_HOST=0.0.0.0) — laisser vide ici
# JARVIS_GPU_NODE_HOST=
# Port du serveur web local (défaut 8600)
# COCKPIT_PORT=8600
```

Ollama local est déjà attendu sur `127.0.0.1:11434` (valeur par défaut). Dans
LM Studio, activez le serveur local (*Developer › Local Server*, port 1234) et
chargez un modèle adapté à la GTX 1660 SUPER (4 Go de VRAM : modèles 3B–4B
quantifiés Q4, ou 7B–8B en déchargement partiel).

## Ce qui n'est pas disponible sous Windows

L'application a été écrite pour un rig Linux (GNOME/Wayland, tmux, systemd
`--user`, `loginctl`, montages `/media`, terminaux PTY). Sous Windows ces
fonctions passent par la couche de compatibilité (`sys.platform == "win32"`)
et se dégradent proprement :

| Fonction Linux | Comportement Windows |
|----------------|----------------------|
| Sessions **tmux** (multiplexeur, onglet Terminal) | non disponibles ; ouverture d'un **Windows Terminal** / `cmd.exe` à la place, les listes de sessions sont vides |
| **systemd --user** (services Ollama, cockpit, exporteur) | pas de services ; les états affichent « indisponible » et le serveur `:8600` se lance par le raccourci *Web* |
| `loginctl`, sessions GNOME/Wayland, `wmctrl`, `xdotool` | ignorés (onglet Bureau en lecture seule) |
| Terminaux **PTY** (`pty`, `termios`) | remplacés par `subprocess` avec tubes ; pas de terminal interactif intégré |
| Montages `/media`, `/storage`, disques VHDX (`bin/jarvis-cockpit-vhdx`) | non gérés ; sauvegarde disque à faire à la main |
| `nvidia-smi` | fonctionne (`C:\Windows\System32\nvidia-smi.exe`) ; l'Intel HD 4600 n'est pas remontée |
| Scripts shell `cockpit\*.sh`, `bin\*` | non exécutés directement ; certains passent par `bash.exe` de Git for Windows ou par WSL (`wsl.exe`) quand la fonction le prévoit |
| Notifications, `xdg-open` | `os.startfile` / navigateur par défaut Windows |

Si une fonctionnalité vous manque, lancez `JARVIS-Cockpit.cmd` : le détail des
replis choisis s'affiche dans la console et dans le journal.

## Dépannage

- **Rien ne se passe au double-clic** : ouvrez
  `%USERPROFILE%\jarvis\logs\cockpit-gui.log`, ou lancez `JARVIS-Cockpit.cmd`.
- **« .venv absent »** : relancez `install.ps1`.
- **`ModuleNotFoundError: PyQt6`** : le venv a été créé avec un autre Python ;
  `install.ps1 -Reinstaller`.
- **Le port 8600 est déjà pris** : `set COCKPIT_PORT=8601` puis relancer, ou
  fermer l'ancienne instance (`Get-Process python* | Stop-Process`).
- **Icône absente sur le raccourci** : supprimez `icons\jarvis_cockpit.ico` et
  relancez `install.ps1` (l'icône est reconstruite) ; Windows met parfois son
  cache d'icônes à jour après une déconnexion.
- **Mise à jour du code** : `git pull` puis `install.ps1` (met à jour les
  dépendances et les raccourcis).
