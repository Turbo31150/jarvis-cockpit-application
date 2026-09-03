# JARVIS COCKPIT — VERSION PORTABLE

Application de bureau JARVIS Cockpit (15 onglets, PyQt6) exécutable depuis
une clé USB, un disque externe ou un disque virtuel, sur n'importe quelle
machine Linux — sans installation.

## Démarrer

```bash
./JARVIS-COCKPIT.sh              # application de bureau
./JARVIS-COCKPIT.sh --web        # serveur seul + navigateur sur :8600
./JARVIS-COCKPIT.sh --verifier   # contrôle les prérequis, ne lance rien
```

## Comment la portabilité est obtenue

Le lanceur déduit sa racine de **sa propre position** (`readlink -f "$0"`),
puis pose `JARVIS_COCKPIT_ROOT`. Toute l'application lit ses chemins depuis
là. Aucun chemin absolu ne subsiste dans le code actif — vérifié le
2026-09-03 : `grep -rn '/home/pamerys'` sur `serveur.py`, `gui_app.py`,
`core/` et `ui/` ne rend plus rien.

`JARVIS_COCKPIT_ROOT` est une variable **dédiée**, distincte de `JARVIS_HOME`
que `~/.profile` exporte déjà vers `~/jarvis` : les confondre rendait le mode
portable toujours actif, y compris sur la machine d'origine.

Les données écrites (logs, bases) restent dans `jarvis/` **à côté du
lanceur**, sur le support — jamais dans le home de la machine hôte.

## Le seul prérequis : PyQt6

PyQt6 n'est **pas** embarqué : ~100 Mo, et il dépend des bibliothèques
graphiques de la machine hôte. `--verifier` le signale clairement.

```bash
sudo apt install python3-pyqt6     # Debian / Ubuntu
```

Sans PyQt6, `--web` donne le **même cockpit** dans un navigateur : le serveur
n'a besoin que de la bibliothèque standard de Python 3.

## Support en lecture seule

L'application démarre, mais ne conserve rien entre deux sessions.
`--verifier` le dit avant que vous ne le découvriez à l'usage.
