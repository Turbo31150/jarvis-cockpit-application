#!/usr/bin/env bash
# =============================================================================
# install-cockpit.sh — installe le JARVIS MASTER COCKPIT sur une machine du parc
#
# Ecrit le 20/08/2026 pour deployer le cockpit de M4 vers rem-linux.
# Deux facades installees :
#   · COCKPIT      :8600  — PWA de pilotage (cockpit/serveur.py), STT/TTS, applis
#   · WIDGET       :8899  — dashboard "ce que le systeme fait vraiment"
#   · TTX          tmux   — multiplexeur 14 fenetres (bin/ttx)
#
# CONTRAT :
#   - idempotent : rejouable sans rien casser
#   - non destructif : ne touche JAMAIS a un depot git existant ni aux bases
#   - portable : aucun /home/<machine> en dur, tout passe par $HOME
#   - 0 dependance : bibliotheque standard python3 uniquement
#
# Usage :  ./install-cockpit.sh [--sans-service] [--port-widget N] [--port-cockpit N]
# =============================================================================
set -uo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"   # racine du depot
DST="$HOME/jarvis"
PORT_WIDGET="${PORT_WIDGET:-8899}"
PORT_COCKPIT="${PORT_COCKPIT:-8600}"
AVEC_SERVICE=1

while [ $# -gt 0 ]; do
  case "$1" in
    --sans-service)  AVEC_SERVICE=0 ;;
    --port-widget)   PORT_WIDGET="$2"; shift ;;
    --port-cockpit)  PORT_COCKPIT="$2"; shift ;;
    -h|--help)
      echo "Usage: ./install-cockpit.sh [--sans-service] [--port-widget N] [--port-cockpit N]"
      echo "Installe le JARVIS Master Cockpit et le planning widget."
      exit 0
      ;;
    *) echo "option inconnue : $1"; exit 2 ;;
  esac
  shift
done

ok(){   echo -e "  \033[32m✓\033[0m $*"; }
ko(){   echo -e "  \033[31m✗\033[0m $*"; }
warn(){ echo -e "  \033[33m!\033[0m $*"; }
titre(){ echo -e "\n\033[1m== $* ==\033[0m"; }

titre "Prerequis"
command -v python3 >/dev/null || { ko "python3 absent — installation impossible"; exit 1; }
ok "python3 $(python3 -V 2>&1 | cut -d' ' -f2)"
command -v sqlite3 >/dev/null && ok "sqlite3 present" || warn "sqlite3 absent (le widget utilise le module python, ce n'est pas bloquant)"
command -v tmux >/dev/null && ok "tmux present" || warn "tmux absent — la fenetre ttx ne sera pas utilisable"

titre "Arborescence"
for d in "$DST/bin" "$DST/logs" "$DST/data/task_results" "$DST/cockpit" "$HOME/bin"; do
  mkdir -p "$d" && ok "$d"
done

titre "Fichiers du cockpit"
poser(){  # poser <relatif-depot> <destination>
  local rel="$1" dest="$2"
  if [ ! -e "$SRC/$rel" ]; then warn "absent du depot (optionnel) : $rel"; return 0; fi
  mkdir -p "$(dirname "$dest")"
  if cmp -s "$SRC/$rel" "$dest" 2>/dev/null; then ok "$rel (deja a jour)"; return 0; fi
  [ -e "$dest" ] && cp -a "$dest" "$dest.bak-$(date +%Y%m%d-%H%M%S)"
  cp -a "$SRC/$rel" "$dest" && chmod +x "$dest" 2>/dev/null
  ok "$rel -> $dest"
}
poser cockpit/serveur.py            "$DST/cockpit/serveur.py"
poser cockpit/app.py                "$DST/cockpit/app.py"
poser cockpit/gui_app.py            "$DST/cockpit/gui_app.py"
poser cockpit/terminaux.py          "$DST/cockpit/terminaux.py"
poser cockpit/launch_gui.sh         "$DST/cockpit/launch_gui.sh"
poser cockpit/launch_web_cockpit.sh "$DST/cockpit/launch_web_cockpit.sh"
for sh_file in "$SRC"/cockpit/*.sh; do
  [ -f "$sh_file" ] || continue
  bsh="$(basename "$sh_file")"
  [ "$bsh" = "install-cockpit.sh" ] && continue
  poser "cockpit/$bsh" "$DST/cockpit/$bsh"
done
for f in index.html turbo.html turbo-os.html modeles.html presentation.html \
         carte-mentale.html audit-chantier.html manifest.json sw.js \
         icone.png icone-192.png qr.png; do
  [ -e "$SRC/cockpit/web/$f" ] && poser "cockpit/web/$f" "$DST/cockpit/web/$f"
done
if [ -d "$SRC/cockpit/web/vendor" ]; then
  mkdir -p "$DST/cockpit/web/vendor"
  cp -a "$SRC/cockpit/web/vendor/"* "$DST/cockpit/web/vendor/" 2>/dev/null || true
  ok "cockpit/web/vendor -> $DST/cockpit/web/vendor"
fi
if [ ! -L "$DST/cockpit" ]; then
  if [ -d "$SRC/cockpit/core" ]; then
    mkdir -p "$DST/cockpit/core"
    cp -a "$SRC/cockpit/core/"* "$DST/cockpit/core/" 2>/dev/null || true
    ok "cockpit/core -> $DST/cockpit/core"
  fi
  if [ -d "$SRC/cockpit/ui" ]; then
    mkdir -p "$DST/cockpit/ui"
    cp -a "$SRC/cockpit/ui/"* "$DST/cockpit/ui/" 2>/dev/null || true
    ok "cockpit/ui -> $DST/cockpit/ui"
  fi
  if [ -d "$SRC/cockpit/web" ]; then
    mkdir -p "$DST/cockpit/web"
    cp -a "$SRC/cockpit/web/"* "$DST/cockpit/web/" 2>/dev/null || true
    ok "cockpit/web -> $DST/cockpit/web"
  fi
fi
poser bin/jarvis-cockpit-app        "$DST/bin/jarvis-cockpit-app"
poser bin/jarvis-cockpit.sh         "$DST/bin/jarvis-cockpit.sh"
poser bin/jarvis-planning-widget.py "$DST/bin/jarvis-planning-widget.py"
poser bin/jarvis-cockpit-vhdx       "$DST/bin/jarvis-cockpit-vhdx"
poser bin/jarvis-cockpit-exporter   "$DST/bin/jarvis-cockpit-exporter"
poser bin/ttx                       "$DST/bin/ttx"
poser bin/ttx                       "$HOME/bin/ttx"
poser bin/swarm-watch.sh            "$DST/bin/swarm-watch.sh"
poser bin/m6-watch.sh               "$DST/bin/m6-watch.sh"
poser scripts/planning_mega_m4.py   "$DST/scripts/planning_mega_m4.py"

titre "Base de tâches (jarvis_master.db)"
DB="$DST/jarvis_master.db"
python3 - "$DB" <<'PY'
import sqlite3, sys, os
db = sys.argv[1]
neuve = not os.path.exists(db)
c = sqlite3.connect(db)
c.execute("""CREATE TABLE IF NOT EXISTS tasks (
  id INTEGER PRIMARY KEY AUTOINCREMENT, parent_id INTEGER, title TEXT, context TEXT,
  status TEXT DEFAULT 'pending', progress INTEGER DEFAULT 0, agent TEXT, machine TEXT,
  score REAL, created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP, biblio_preload TEXT)""")
c.execute("""CREATE TABLE IF NOT EXISTS plan (
  id INTEGER PRIMARY KEY AUTOINCREMENT, titre TEXT, statut TEXT DEFAULT 'a_faire',
  cree_le DATETIME DEFAULT CURRENT_TIMESTAMP)""")
existing_cols = {row[1] for row in c.execute("PRAGMA table_info(tasks)").fetchall()}
for col_name, col_type in (
    ("parent_id", "INTEGER"), ("agent", "TEXT"), ("score", "REAL"),
    ("biblio_preload", "TEXT"), ("machine", "TEXT"), ("context", "TEXT"),
    ("progress", "INTEGER DEFAULT 0"),
):
    if col_name not in existing_cols:
        try:
            c.execute(f"ALTER TABLE tasks ADD COLUMN {col_name} {col_type}")
        except Exception:
            pass
for idx, col in (("idx_tasks_status","status"),("idx_tasks_updated","updated_at"),
                 ("idx_tasks_agent","agent"),("idx_tasks_created_at","created_at")):
    try:
        c.execute(f"CREATE INDEX IF NOT EXISTS {idx} ON tasks({col})")
    except Exception:
        pass
c.commit()
n = c.execute("SELECT count(*) FROM tasks").fetchone()[0]
print(f"  base {'CREEE' if neuve else 'deja presente'} — {n} tache(s)")
PY
[ -f "$DB" ] && ok "$DB"

titre "Services systemd (--user)"
if [ "$AVEC_SERVICE" = "1" ] && command -v systemctl >/dev/null; then
  mkdir -p "$HOME/.config/systemd/user"
  PY_BIN="/usr/bin/python3"
  [ -x "$HOME/jarvis/.venv/bin/python3" ] && PY_BIN="%h/jarvis/.venv/bin/python3"
  cat > "$HOME/.config/systemd/user/jarvis-planning-widget.service" <<UNIT
[Unit]
Description=JARVIS Planning Widget — backend dashboard :$PORT_WIDGET
After=default.target
StartLimitBurst=5
StartLimitIntervalSec=120

[Service]
Type=simple
ExecStart=$PY_BIN %h/jarvis/bin/jarvis-planning-widget.py $PORT_WIDGET
WorkingDirectory=%h/jarvis
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1
StandardOutput=append:%h/jarvis/logs/planning-widget.log
StandardError=append:%h/jarvis/logs/planning-widget.log

[Install]
WantedBy=default.target
UNIT
  if [ ! -f "$HOME/.config/systemd/user/jarvis-cockpit.service" ]; then
    cat > "$HOME/.config/systemd/user/jarvis-cockpit.service" <<UNIT
[Unit]
Description=JARVIS Cockpit — pilotage du cluster (PWA :$PORT_COCKPIT)
After=network.target

[Service]
Type=simple
WorkingDirectory=%h/jarvis/cockpit
ExecStart=$PY_BIN %h/jarvis/cockpit/serveur.py
Restart=always
RestartSec=5
Environment=COCKPIT_PORT=$PORT_COCKPIT
StandardOutput=append:%h/jarvis/logs/cockpit.log
StandardError=append:%h/jarvis/logs/cockpit.log

[Install]
WantedBy=default.target
UNIT
    ok "unit jarvis-cockpit.service generee"
  else
    ok "unit jarvis-cockpit.service preservee (existante)"
  fi
  ok "units ecrites"
  systemctl --user daemon-reload 2>/dev/null
  for s in jarvis-planning-widget jarvis-cockpit; do
    systemctl --user enable --now "$s.service" >/dev/null 2>&1 \
      && ok "$s demarre" || warn "$s : demarrage refuse (voir journalctl --user -u $s)"
  done
  # survit a la deconnexion de la session
  command -v loginctl >/dev/null && loginctl enable-linger "$USER" 2>/dev/null \
    && ok "linger actif (les services survivent au logout)" || true
else
  warn "installation sans service — lancement manuel :"
  echo "      python3 ~/jarvis/bin/jarvis-planning-widget.py $PORT_WIDGET &"
  echo "      COCKPIT_PORT=$PORT_COCKPIT python3 ~/jarvis/cockpit/serveur.py &"
fi

titre "Verification au sol"
sleep 3
for p in "$PORT_WIDGET:widget" "$PORT_COCKPIT:cockpit"; do
  port="${p%%:*}"; nom="${p##*:}"
  code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 8 "http://127.0.0.1:$port/" 2>/dev/null)
  case "$code" in
    200|301|302) ok "$nom  :$port  repond HTTP $code" ;;
    *)           ko "$nom  :$port  ne repond pas (code='$code')" ;;
  esac
done
IP_TS=$(command -v tailscale >/dev/null && tailscale ip -4 2>/dev/null | head -1)
[ -n "${IP_TS:-}" ] && echo -e "\n  Acces depuis le tailnet :\n    widget  → http://$IP_TS:$PORT_WIDGET\n    cockpit → http://$IP_TS:$PORT_COCKPIT"
echo -e "\n\033[1m✅ Cockpit installe.\033[0m  Multiplexeur tmux : \033[1m~/bin/ttx\033[0m"
