---
name: run-jarvis-cockpit-application
description: Build, run, drive, screenshot and test JARVIS Cockpit (PyQt6 desktop app, :8600 web server, Textual TUI). Use when asked to start/run/launch the cockpit, take a screenshot of a tab, click a button, check a tab's text, hit the web API, run the TUI, or run tests — on Windows (.venv) or Linux/WSL.
---

JARVIS Cockpit is one Python code base with three binaries: the PyQt6 desktop app
(17 pages), an HTTP/JSON server (`jarvis_cockpit_launcher.pyw --web`, :8600) and a
Textual TUI (`--tui`). Drive the GUI **headless** with
`.claude/skills/run-jarvis-cockpit-application/driver.py` (offscreen Qt: real
window, real tabs, `click`, `text`, PNG via `QWidget.grab()`, modal dialogs
auto-closed). Drive the server with `curl`, the TUI with `tmux`.

All paths are relative to the repo root. Two Pythons exist and both were verified:

| Where | Python | Repo root |
|---|---|---|
| Windows (or from WSL via `cmd.exe /c`) | `.venv\Scripts\python.exe` (3.13) | `C:\Users\clair\jarvis-cockpit-application` |
| Linux / WSL | `~/.venvs/cockpit/bin/python` (3.12) | `/mnt/c/Users/clair/jarvis-cockpit-application` |

## Prerequisites

Linux/WSL (Ubuntu 24.04 — libGL/EGL/xkbcommon/fontconfig/dbus were already present;
the emoji font was the only thing missing, without it every tab title renders as □):

```bash
sudo apt-get install -y fonts-noto-color-emoji && fc-cache -f
python3 -m venv ~/.venvs/cockpit && ~/.venvs/cockpit/bin/pip install -q -r requirements.txt
```

Windows: `.venv` already exists (`install.ps1` creates it: Python 3.13 + PyQt6,
textual, psutil, requests, pywinpty). No build step — pure Python.

## Run (agent path): the GUI driver

Smoke = build the real window, visit all 17 pages, one PNG per page + `smoke.json`:

```bash
# Linux / WSL  (≈25 s, window built in ≈4 s)
cd /mnt/c/Users/clair/jarvis-cockpit-application
~/.venvs/cockpit/bin/python .claude/skills/run-jarvis-cockpit-application/driver.py smoke --out /tmp/jarvis-cockpit-driver-linux

# Windows Python, called from WSL (≈20 s) — PNGs land in %TEMP%\jarvis-cockpit-driver
cmd.exe /c 'C:\Users\clair\jarvis-cockpit-application\.claude\skills\run-jarvis-cockpit-application\driver.cmd smoke'
```

Expected tail: `17 pages, 0 indisponible(s) [] … bilan → …/smoke.json`. A page whose
constructor raised shows `KO` and class `_OngletIndisponible`; `--strict` turns that
into exit code 1.

One-shot commands (`-c`, repeatable, run in order):

```bash
~/.venvs/cockpit/bin/python .claude/skills/run-jarvis-cockpit-application/driver.py \
  --out /tmp/jarvis-cockpit-driver-linux -c "go apps" -c "click Réinventorier" -c "text 200" -c "ss apps.png"
```

From WSL towards the Windows Python, `-c "go hud"` loses its quotes inside
`cmd.exe /c '…'` (`invalid choice: 'hud"'`): pipe the commands into `repl` instead —

```bash
printf 'go hud\nbuttons\nss hud-run.png\nquit\n' | cmd.exe /c 'C:\Users\clair\jarvis-cockpit-application\.claude\skills\run-jarvis-cockpit-application\driver.cmd repl'
```

REPL under tmux (Windows Python shown; for Linux replace the command with the venv python + `driver.py repl`):

```bash
tmux new-session -d -s jc -x 200 -y 50 "cmd.exe /c 'C:\\Users\\clair\\jarvis-cockpit-application\\.claude\\skills\\run-jarvis-cockpit-application\\driver.cmd' repl"
sleep 12                                   # wait for "[driver] prêt"
tmux send-keys -t jc "go apps" Enter; sleep 3
tmux send-keys -t jc "click Réinventorier" Enter; sleep 4
tmux send-keys -t jc "ss apps-apres-clic.png" Enter; sleep 3
tmux capture-pane -p -t jc -S -60
tmux send-keys -t jc "quit" Enter         # the tmux session ends with the driver
```

Driver commands: `tabs` · `go <index|title or class substring>` (e.g. `go apps`,
`go terminal`, `go 16`) · `buttons` (text/enabled/tooltip of the current page) ·
`click <button text>` (exact, then case-insensitive substring; a disabled button
returns `"clique": false` + its tooltip instead of clicking) · `text [n]` (visible
labels/text areas/table cells) · `ss [file.png]` · `wait [ms]` · `dialogs` ·
`eval <python>` (`win`, `app`, `page`, `d`) · `smoke` · `quit`.
Options: `--show` (real window: WSLg or the Windows desktop instead of offscreen),
`--home DIR` (JARVIS_HOME), `--settle MS` (event-loop time after each command, 400).

Verified flows this session: `go apps` → `click Réinventorier` → `text` shows
`309 entrées · 15 dossiers` (Windows) / `1 entrées` (WSL); `click Claude Desktop` →
`désactivé`, tooltip `Introuvable sur cette machine`; `go terminal` → `click Exécuter`;
`eval …QMessageBox.information(win,'Test modal','coucou')` → closed by the watchdog
and listed by `dialogs`.

## Run: the real window on the Windows desktop (`real.ps1`)

When the change must be seen in the user's own instance (non-admin, WT as default
terminal, real launchers), drive the real window instead of offscreen:

```bash
# restart non-admin (explorer → .cmd → .venv pythonw), PrintWindow capture, UIA click on a button by name
powershell.exe -NoProfile -ExecutionPolicy Bypass -File 'C:\Users\clair\jarvis-cockpit-application\.claude\skills\run-jarvis-cockpit-application\real.ps1' -Restart -Click 'Terminal JARVIS'
# capture only (instance already running)
powershell.exe -NoProfile -ExecutionPolicy Bypass -File 'C:\Users\clair\jarvis-cockpit-application\.claude\skills\run-jarvis-cockpit-application\real.ps1' -Out 'C:\Users\clair\AppData\Local\Temp\jarvis-cockpit-driver\real-2.png'
```

Verified: `-Restart -Click 'Terminal JARVIS'` → window `JARVIS MASTER COCKPIT — POSTE DE
COMMANDE UNIFIÉ (M4-PAMERYS)`, 1562×1035 PNG, then `pwsh.exe -NoLogo -NoExit -Command
"$Host.UI.RawUI.WindowTitle = 'Terminal JARVIS'"` appears as a child of the cockpit
with its console handed to Windows Terminal (`OpenConsole.exe -Embedding`) — no
0x80070002. `Start-Process explorer.exe file.pyw` does **not** launch the app (nothing
happens); the `.cmd` indirection is what works. The script carries a UTF-8 BOM on
purpose (PowerShell 5.1 parses a BOM-less UTF-8 file as ANSI and chokes on « »).

## Run: web server (`--web`)

```bash
# Windows Python from WSL — web.cmd [port] blocks: run it in the background, probe with Windows curl
cmd.exe /c 'C:\Users\clair\jarvis-cockpit-application\.claude\skills\run-jarvis-cockpit-application\web.cmd 8601' &
sleep 6
/mnt/c/Windows/System32/curl.exe -s http://127.0.0.1:8601/api/status | head -c 300
/mnt/c/Windows/System32/curl.exe -s http://127.0.0.1:8601/api/apps/all | head -c 300
# stop: kill the python whose command line contains "launcher.pyw --web"
powershell.exe -NoProfile -Command "Get-CimInstance Win32_Process | ? { \$_.CommandLine -match 'launcher\.pyw.*--web' } | % { Stop-Process -Id \$_.ProcessId -Force }"

# Linux / WSL
COCKPIT_PORT=8602 JARVIS_HOME=/home/turbo/jarvis ~/.venvs/cockpit/bin/python jarvis_cockpit_launcher.pyw --web &
curl -s http://127.0.0.1:8602/api/status | head -c 160
curl -s http://127.0.0.1:8602/api/databases | head -c 160
pkill -f '[l]auncher.pyw --web'
```

The server logs `démarré sur http://127.0.0.1:<port> (bind 0.0.0.0)` and serves the
web UI at `/` (`<title>JARVIS MASTER COCKPIT OS…`). Routes: `/api/status`,
`/api/apps/all`, `/api/databases`, `/api/mcps`, `/api/swarm`, `/api/tasks`… (see
`cockpit/serveur.py`, `do_GET`). It binds 0.0.0.0, so a Windows-side server is also
reachable from WSL at `http://$(ip route | awk '/default/{print $3}'):<port>/`.

## Run: TUI (`cockpit/app.py`, Textual)

```bash
tmux new-session -d -s jtui -x 160 -y 45 "cd /mnt/c/Users/clair/jarvis-cockpit-application && JARVIS_HOME=/home/turbo/jarvis PYTHONPATH=cockpit ~/.venvs/cockpit/bin/python cockpit/app.py"
sleep 10; tmux capture-pane -p -t jtui | head -30      # header "JARVIS MASTER COCKPIT — M4 NATIVE", 6 tabs
tmux send-keys -t jtui q                               # q quits; 1..6 switch tabs
```

Do **not** redirect its stderr: Textual paints the screen on stderr here — with
`2>file` the pane stays blank and the ANSI frames land in the file.

## Direct invocation (PRs touching `cockpit/core/*`)

```bash
cd /mnt/c/Users/clair/jarvis-cockpit-application
PYTHONPATH=cockpit ~/.venvs/cockpit/bin/python -c "from core import platform_compat as pc; print(pc.IS_WINDOWS, pc.IS_WSL, pc.terminal_argv('echo hi', title='T')[0])"
```

Same on Windows via a `.cmd` file (see Gotchas) with `set "PYTHONPATH=…\cockpit"` — `tests.cmd` in this directory is the model.

## Test

```bash
cd cockpit && ~/.venvs/cockpit/bin/python -m unittest tests_platform_compat -q     # 56 tests, ≈11 s, 3 skipped
cmd.exe /c 'C:\Users\clair\jarvis-cockpit-application\.claude\skills\run-jarvis-cockpit-application\tests.cmd'   # Windows Python: 56 OK, ≈30 s
```

## Run (human path)

Windows: `JARVIS-Cockpit.cmd` (console stays open on error), or the Desktop/Start-menu
shortcut → `jarvis_cockpit_launcher.pyw` under `pythonw.exe` (log:
`%USERPROFILE%\jarvis\logs\cockpit-gui.log`). Linux rig: `bin/jarvis-cockpit-app`.
Single instance: a second launch just raises the first window (QLocalServer IPC).
Useless headless — use the driver.

## Gotchas

- **Offscreen on Windows renders every glyph as □** unless `QT_QPA_FONTDIR=C:\Windows\Fonts`
  (the offscreen plugin uses the FreeType font database). `driver.py` sets it; each
  unloadable `.fon` then logs `QFontEngineFT: Failed to create FreeType font engine`
  (~20 lines, harmless — the driver filters them, along with `propagateSizeHints`).
- **Emoji in WSL** need `fonts-noto-color-emoji`; text was fine with DejaVu alone.
- **Port 8600 may already be taken by a WSL-side `serveur.py`** (visible on Windows
  as `wslrelay.exe` owning the port — `Get-NetTCPConnection -LocalPort 8600`). Python's
  HTTPServer still binds thanks to SO_REUSEADDR, so `curl 127.0.0.1:8600` silently
  answers from the *other* server. Always pick a fresh `COCKPIT_PORT` and check
  `ss -ltn | grep 860` (WSL) before trusting a response.
- **Windows Python from WSL**: always go through a `.cmd` file run with `cmd.exe /c`
  (`driver.cmd`, `web.cmd`, `tests.cmd` here). A one-string inline form
  `cmd.exe /c 'cd /d … && set "X=1" && python …'` ran but produced no output at all
  through WSL interop, and unquoted `set X=1 &&` leaves a trailing space in the value
  (`invalid PYTHONUTF8 value`). Files avoid both.
- **`pkill -f 'launcher.pyw --web'` kills your own shell** (its command line matches):
  use the `[l]auncher` bracket trick.
- **Everything run through WSL interop is elevated** (PowerShell/cmd inherit admin).
  To test a Windows launcher as the user would (non-admin), run
  `explorer.exe 'C:\...\script.cmd'` and read a result file — that is how the
  `wt.exe`/`elevate: true` bug (0x80070002) was reproduced; see
  `cockpit/docs/REPRISE_SESSION_2026-09-16.md`.
- The driver renames the single-instance IPC socket (`jarvis_cockpit_driver_<pid>`), so
  it can run while the real cockpit is open. Windows-only tabs show tmux/GNOME as
  "indisponible" by design; on WSL the same tabs see tmux and take the Linux path.
- `--show` on WSL opens a real WSLg window; on Windows a real desktop window. Only
  use it when a human is looking.

## Troubleshooting

- `[erreur] ValueError: onglet introuvable : 'apps'` → titles are French with emoji
  (`🚀 Applications Bureau`); `go` also matches the class name (`TabApps`), so
  `go apps`, `go applications` or `go 4` all work.
- `[erreur] ValueError: bouton introuvable` → run `buttons` on that page; texts
  carry emoji prefixes (`🔄 Réinventorier`) — substring match ignores them.
- Blank tmux pane for the TUI → you redirected stderr; relaunch without `2>`.
- `curl: (7)`/connection closed on `:1234` → LM Studio's server is off; the cockpit
  still starts (tabs degrade to "M6 INJOIGNABLE").
- Driver exits with code 2 and a traceback before `[driver] fenêtre construite` →
  an import failed in `gui_app`; run the direct-invocation one-liner to see it.
