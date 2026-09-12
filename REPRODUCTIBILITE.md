# 🔄 Guide de Reproductibilité à l'Infini — JARVIS Cockpit Application

> **Dépôt GitHub Privé** : `https://github.com/Turbo31150/jarvis-cockpit-application.git`  
> **Architecture** : 100% Souveraine, Relocalisable, Zéro Dépendance Bloquante

Ce dépôt contient l'intégralité du **Cockpit Bureau JARVIS** (application native PyQt6 à 15 onglets, interface TUI Textual, et serveur d'application Web REST :8600).

---

## 1. Déploiement en 1 Ligne (N'importe quelle machine Linux)

```bash
git clone https://github.com/Turbo31150/jarvis-cockpit-application.git
cd jarvis-cockpit-application
./install.sh
```

L'installateur configure automatiquement :
1. L'environnement virtuel isolé `.venv/`
2. Les dépendances GUI et TUI (`PyQt6`, `textual`, `requests`, `psutil`)
3. Les droits d'exécution sur les lanceurs universels
4. L'arborescence des données souveraines locales

---

## 2. Modes d'Exécution

### Mode A : Application Bureau Native (PyQt6 - 15 Onglets)
```bash
./portable/JARVIS-COCKPIT.sh
# ou directement :
.venv/bin/python3 cockpit/gui_app.py
```
*Si la session est en X11/Wayland avec Qt, forcez si besoin :* `QT_QPA_PLATFORM=xcb ./portable/JARVIS-COCKPIT.sh`

### Mode B : Serveur Web REST Cockpit (:8600)
Accessible depuis n'importe quel navigateur sur `http://localhost:8600` ou depuis mobile/tablette sur le LAN :
```bash
./portable/JARVIS-COCKPIT.sh --web
# ou directement :
.venv/bin/python3 cockpit/serveur.py
```

### Mode C : Dashboard Terminal TUI (0% Graphique, 100% SSH/Terminal)
```bash
.venv/bin/python3 cockpit/app.py
```

---

## 3. Structure Portative du Dépôt

```
jarvis-cockpit-application/
├── install.sh                  # Script d'installation autonome automatique
├── requirements.txt            # Dépendances Python versionnées
├── REPRODUCTIBILITE.md         # Guide de déploiement et reproduction
├── README.md                   # Documentation d'architecture
├── bin/
│   ├── jarvis-cockpit-app      # Lanceur en ligne de commande
│   └── ttx                     # Lanceur Textual interactif
├── cockpit/
│   ├── gui_app.py              # Application PyQt6 principale (15 onglets)
│   ├── app.py                  # Application TUI Textual terminal
│   ├── serveur.py              # Serveur HTTP REST natif (:8600)
│   ├── core/                   # Moteurs (Inférence, Config, Bases, Inventaire)
│   ├── ui/                     # Vues et onglets modulaires
│   └── web/                    # Templates et assets web du Cockpit
├── icons/                      # Icônes vectorielles et PNG officielles
└── portable/
    ├── JARVIS-COCKPIT.sh       # Lanceur relocalisable universel (USB / VM / VHDX)
    └── JARVIS-COCKPIT.desktop  # Raccourci de bureau Linux
```

---

## 4. Garanties de Souveraineté & Isolation

* **Relocalisation automatique** : Tous les scripts calculent leur racine par `$(dirname "$(readlink -f "$0")")` sans jamais dépendre de chemins codés en dur dans `/home/turbo`.
* **Fallback gracieux** : Si une base de données ou un GPU n'est pas présent sur la machine hôte, l'application démarre sans planter et signale l'état dans l'inventaire.
* **Privé & Sécurisé** : Réservé exclusivement à votre compte GitHub privé `Turbo31150`.
