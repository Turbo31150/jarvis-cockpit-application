#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TURBO OS — APPLICATION MANAGER
==============================
ApplicationRegistry, ApplicationController & ApplicationHealth :
Contrôle et observabilité des applications Linux réelles :
  - GUI (X11 / Wayland / xdotool)
  - Process (PID, CPU, Mémoire, SIGTERM, SIGKILL, SIGSTOP, SIGCONT)
  - Service (systemd user services)
  - Browser (CDP / Chrome)
  - Terminal (tmux / terminaux)

Directives :
  - Application = Process + Healthcheck + Interface/API/Window.
  - APPLICATION_STATUS : REGISTERED, STARTING, READY, RUNNING, STOPPING, STOPPED, ERROR, CRASHED, UNAVAILABLE, UNKNOWN.
  - (READY ≠ RUNNING).
  - Aucune application hors radar.
"""

from __future__ import annotations

import os
import re
import sys
import time
import signal
import shutil
import socket
import logging
import subprocess
import threading
from typing import Dict, Any, List, Optional, Tuple

try:
    from .system_state import get_system_state, ApplicationStatus, HealthStatus
    from .apps_registry import scan_all_applications, launch_application, cible_dispo
except ImportError:
    from system_state import get_system_state, ApplicationStatus, HealthStatus
    from apps_registry import scan_all_applications, launch_application, cible_dispo

logger = logging.getLogger("TurboOS.AppManager")


# ─── APPLICATION HEALTH PROBE ────────────────────────────────────────────────

class ApplicationHealth:
    """Sonde l'état réel et mesurable d'une application Linux."""

    @staticmethod
    def is_pid_running(pid: Optional[int]) -> bool:
        if not pid or pid <= 0:
            return False
        try:
            # os.kill(pid, 0) teste si le processus existe et répond aux signaux
            os.kill(pid, 0)
            return True
        except (ProcessLookupError, PermissionError):
            return False

    @staticmethod
    def get_proc_stats(pid: int) -> Dict[str, Any]:
        """Extrait les métriques CPU/Mémoire réelles depuis /proc."""
        stats: Dict[str, Any] = {"pid": pid, "is_alive": False, "rss_kb": 0, "cmdline": ""}
        if not pid:
            return stats
        proc_dir = f"/proc/{pid}"
        if not os.path.isdir(proc_dir):
            return stats

        stats["is_alive"] = True
        try:
            with open(f"{proc_dir}/cmdline", "r", errors="ignore") as f:
                stats["cmdline"] = f.read().replace("\x00", " ").strip()
        except Exception:
            pass

        try:
            with open(f"{proc_dir}/status", "r", errors="ignore") as f:
                for line in f:
                    if line.startswith("VmRSS:"):
                        parts = line.split()
                        if len(parts) >= 2 and parts[1].isdigit():
                            stats["rss_kb"] = int(parts[1])
                            stats["rss_mb"] = round(stats["rss_kb"] / 1024.0, 1)
                        break
        except Exception:
            pass

        return stats

    @staticmethod
    def find_window_id_for_pid(pid: int) -> Optional[str]:
        """Trouve l'ID de fenêtre X11 pour un PID via xdotool."""
        if not pid or not shutil.which("xdotool"):
            return None
        try:
            out = subprocess.check_output(
                ["xdotool", "search", "--pid", str(pid)],
                stderr=subprocess.DEVNULL, timeout=1.0
            ).decode().strip()
            wids = out.splitlines()
            return wids[-1] if wids else None
        except Exception:
            return None

    @staticmethod
    def is_port_open(port: int, host: str = "127.0.0.1", timeout: float = 0.5) -> bool:
        """Vérifie si un port réseau d'interface/API répond."""
        try:
            with socket.create_connection((host, port), timeout=timeout):
                return True
        except Exception:
            return False

    @classmethod
    def probe(cls, app: Dict[str, Any]) -> Dict[str, Any]:
        """Probe complet : process, fenêtre X11, port, statut de santé."""
        pid = app.get("pid")
        alive = cls.is_pid_running(pid)
        stats = cls.get_proc_stats(pid) if alive and pid else {}
        win_id = cls.find_window_id_for_pid(pid) if alive and pid else None
        port = app.get("port")
        port_ok = cls.is_port_open(port) if port else None

        health_status = HealthStatus.UNKNOWN.value
        if alive or (app.get("type") == "service" and port_ok):
            health_status = HealthStatus.HEALTHY.value
        elif app.get("status") == ApplicationStatus.RUNNING.value and not alive:
            health_status = HealthStatus.ERROR.value

        return {
            "app_id": app.get("id"),
            "is_alive": alive,
            "pid": pid,
            "stats": stats,
            "window_id": win_id or app.get("window_id"),
            "port_open": port_ok,
            "health": health_status,
            "probed_at": time.time(),
        }


# ─── APPLICATION REGISTRY ────────────────────────────────────────────────────

class ApplicationRegistry:
    """Registre unifié de toutes les applications du système Turbo OS."""

    def __init__(self):
        self._apps: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.RLock()
        self.state = get_system_state()

    def discover_all(self) -> List[Dict[str, Any]]:
        """Scanne le bureau, le cluster, les services et le système."""
        with self._lock:
            # 1. Applications scannées du bureau et lanceurs
            raw_apps = scan_all_applications()
            for item in raw_apps:
                name = item.get("name", "")
                app_id = self._slugify(name)
                dispo = item.get("dispo", True)
                initial_status = ApplicationStatus.READY.value if dispo else ApplicationStatus.UNAVAILABLE.value

                existing = self._apps.get(app_id, {})
                pid = existing.get("pid")
                if pid and ApplicationHealth.is_pid_running(pid):
                    status = ApplicationStatus.RUNNING.value
                else:
                    status = initial_status

                record = {
                    "id": app_id,
                    "name": name,
                    "category": item.get("category", "SYSTÈME & OUTILS"),
                    "type": item.get("type", "desktop"),
                    "exec": item.get("exec", ""),
                    "path": item.get("path", ""),
                    "icon": item.get("icon", "utilities-terminal"),
                    "terminal": item.get("terminal", False),
                    "dispo": dispo,
                    "status": status,
                    "pid": pid,
                    "window_id": existing.get("window_id"),
                    "port": existing.get("port"),
                }
                self._apps[app_id] = record
                self.state.register_entity("application", app_id, status, metadata=record)

            # 2. Services critiques déclarés Turbo OS
            core_services = [
                {"name": "Cockpit Server", "id": "cockpit-server", "port": 8600, "category": "SYSTÈME & OUTILS", "type": "service"},
                {"name": "LM Studio Local 1234", "id": "lmstudio-1234", "port": 1234, "category": "AGENTS & IA", "type": "service"},
                {"name": "LM Studio Local 1235", "id": "lmstudio-1235", "port": 1235, "category": "AGENTS & IA", "type": "service"},
                {"name": "Kokoro TTS", "id": "kokoro-tts", "port": 1250, "category": "MULTIMÉDIA & AUDIO", "type": "service"},
                {"name": "Voice STT Service", "id": "voice-stt", "port": 1270, "category": "MULTIMÉDIA & AUDIO", "type": "service"},
                {"name": "Agent API 1260", "id": "agent-api-1260", "port": 1260, "category": "AGENTS & IA", "type": "service"},
            ]
            for cs in core_services:
                cid = cs["id"]
                is_open = ApplicationHealth.is_port_open(cs["port"])
                st = ApplicationStatus.RUNNING.value if is_open else ApplicationStatus.READY.value
                record = {
                    "id": cid,
                    "name": cs["name"],
                    "category": cs["category"],
                    "type": cs["type"],
                    "exec": "",
                    "path": "",
                    "icon": "network-server",
                    "terminal": False,
                    "dispo": True,
                    "status": st,
                    "pid": None,
                    "window_id": None,
                    "port": cs["port"],
                }
                self._apps[cid] = record
                self.state.register_entity("application", cid, st, metadata=record)

            return list(self._apps.values())

    def get(self, app_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            return self._apps.get(app_id)

    def list_all(self) -> List[Dict[str, Any]]:
        with self._lock:
            if not self._apps:
                self.discover_all()
            return list(self._apps.values())

    def update(self, app_id: str, updates: Dict[str, Any]):
        with self._lock:
            if app_id in self._apps:
                self._apps[app_id].update(updates)

    @staticmethod
    def _slugify(text: str) -> str:
        s = re.sub(r"[^\w\s-]", "", text.lower())
        return re.sub(r"[-\s]+", "-", s).strip("-") or "app"


# ─── APPLICATION CONTROLLER ──────────────────────────────────────────────────

class ApplicationController:
    """Contrôleur de cycle de vie réel pour les applications Linux."""

    def __init__(self, registry: Optional[ApplicationRegistry] = None):
        self.registry = registry or ApplicationRegistry()
        self.state = get_system_state()
        self._lock = threading.RLock()

    def start(self, app_id: str, caller: str = "user") -> Dict[str, Any]:
        """Démarre une application, trace le PID, vérifie la fenêtre et met à jour l'état."""
        with self._lock:
            app = self.registry.get(app_id)
            if not app:
                self.registry.discover_all()
                app = self.registry.get(app_id)
            if not app:
                return {"success": False, "error": f"Application '{app_id}' introuvable"}

            current_status = app.get("status")
            if current_status == ApplicationStatus.RUNNING.value and ApplicationHealth.is_pid_running(app.get("pid")):
                return {"success": True, "message": f"Application '{app['name']}' déjà en cours d'exécution", "pid": app.get("pid")}

            # 1. Transition vers STARTING
            self.state.transition("application", app_id, ApplicationStatus.STARTING.value,
                                  reason=f"Démarrage déclenché par {caller}", updated_by=caller)
            self.registry.update(app_id, {"status": ApplicationStatus.STARTING.value})

            # 2. Exécution du binaire/script
            proc = None
            try:
                exec_cmd = app.get("exec")
                path = app.get("path")
                is_terminal = app.get("terminal", False)

                if is_terminal:
                    term_bin = shutil.which("gnome-terminal") or shutil.which("x-terminal-emulator") or "xterm"
                    proc = subprocess.Popen(
                        [term_bin, "--title", app.get("name", "Turbo App"), "--", "bash", "-lc", exec_cmd or f"bash '{path}'"],
                        start_new_session=True
                    )
                elif path and path.endswith(".desktop") and shutil.which("gio"):
                    # GIO lance en arrière-plan sans donner de PID direct
                    subprocess.Popen(["gio", "launch", path], start_new_session=True,
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                else:
                    cmd = exec_cmd if exec_cmd else f"bash '{path}'"
                    proc = subprocess.Popen(cmd, shell=True, start_new_session=True,
                                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

                pid = proc.pid if proc else None
                time.sleep(0.3)  # Temps d'initialisation X11 / proc

                # 3. Vérification de démarrage effectif
                win_id = ApplicationHealth.find_window_id_for_pid(pid) if pid else None

                self.state.transition("application", app_id, ApplicationStatus.RUNNING.value,
                                      reason="Démarrage réussi", updated_by=caller,
                                      extra={"pid": pid, "window_id": win_id})
                self.registry.update(app_id, {
                    "status": ApplicationStatus.RUNNING.value,
                    "pid": pid,
                    "window_id": win_id,
                })

                return {
                    "success": True,
                    "app_id": app_id,
                    "status": ApplicationStatus.RUNNING.value,
                    "pid": pid,
                    "window_id": win_id,
                    "message": f"Application '{app['name']}' lancée avec succès"
                }

            except Exception as e:
                self.state.transition("application", app_id, ApplicationStatus.ERROR.value,
                                      reason=f"Échec démarrage: {e}", updated_by=caller)
                self.registry.update(app_id, {"status": ApplicationStatus.ERROR.value})
                return {"success": False, "error": f"Erreur de lancement: {e}"}

    def stop(self, app_id: str, force: bool = False, caller: str = "user") -> Dict[str, Any]:
        """Arrête une application de façon propre (SIGTERM) ou forcée (SIGKILL)."""
        with self._lock:
            app = self.registry.get(app_id)
            if not app:
                return {"success": False, "error": f"Application '{app_id}' introuvable"}

            pid = app.get("pid")
            if not pid or not ApplicationHealth.is_pid_running(pid):
                self.state.transition("application", app_id, ApplicationStatus.STOPPED.value,
                                      reason="Processus déjà inactif", updated_by=caller)
                self.registry.update(app_id, {"status": ApplicationStatus.STOPPED.value, "pid": None})
                return {"success": True, "message": "Déjà arrêtée"}

            # Transition STOPPING
            self.state.transition("application", app_id, ApplicationStatus.STOPPING.value,
                                  reason=f"Arrêt demandé par {caller}", updated_by=caller)
            self.registry.update(app_id, {"status": ApplicationStatus.STOPPING.value})

            sig = signal.SIGKILL if force else signal.SIGTERM
            try:
                os.kill(pid, sig)
                # Attente brève de terminaison
                for _ in range(10):
                    if not ApplicationHealth.is_pid_running(pid):
                        break
                    time.sleep(0.1)

                if ApplicationHealth.is_pid_running(pid) and not force:
                    # Force kill si SIGTERM n'a pas suffi
                    os.kill(pid, signal.SIGKILL)

                self.state.transition("application", app_id, ApplicationStatus.STOPPED.value,
                                      reason="Arrêt confirmé", updated_by=caller)
                self.registry.update(app_id, {"status": ApplicationStatus.STOPPED.value, "pid": None, "window_id": None})
                return {"success": True, "app_id": app_id, "status": ApplicationStatus.STOPPED.value}

            except Exception as ex:
                self.state.transition("application", app_id, ApplicationStatus.ERROR.value,
                                      reason=f"Erreur arrêt: {ex}", updated_by=caller)
                return {"success": False, "error": f"Erreur arrêt: {ex}"}

    def pause(self, app_id: str, caller: str = "user") -> Dict[str, Any]:
        """Gèle le processus avec SIGSTOP (pause réelle sans perte de mémoire)."""
        with self._lock:
            app = self.registry.get(app_id)
            if not app:
                return {"success": False, "error": f"Application '{app_id}' introuvable"}
            pid = app.get("pid")
            if not pid or not ApplicationHealth.is_pid_running(pid):
                return {"success": False, "error": "Application non active (pas de PID)"}

            try:
                os.kill(pid, signal.SIGSTOP)
                self.state.transition("application", app_id, ApplicationStatus.READY.value,
                                      reason="Processus mis en pause (SIGSTOP)", updated_by=caller,
                                      extra={"is_paused": True})
                self.registry.update(app_id, {"status": ApplicationStatus.READY.value, "is_paused": True})
                return {"success": True, "app_id": app_id, "paused": True}
            except Exception as e:
                return {"success": False, "error": str(e)}

    def resume(self, app_id: str, caller: str = "user") -> Dict[str, Any]:
        """Dégèle le processus avec SIGCONT."""
        with self._lock:
            app = self.registry.get(app_id)
            if not app:
                return {"success": False, "error": f"Application '{app_id}' introuvable"}
            pid = app.get("pid")
            if not pid or not ApplicationHealth.is_pid_running(pid):
                return {"success": False, "error": "Application non active (pas de PID)"}

            try:
                os.kill(pid, signal.SIGCONT)
                self.state.transition("application", app_id, ApplicationStatus.RUNNING.value,
                                      reason="Processus réactivé (SIGCONT)", updated_by=caller,
                                      extra={"is_paused": False})
                self.registry.update(app_id, {"status": ApplicationStatus.RUNNING.value, "is_paused": False})
                return {"success": True, "app_id": app_id, "running": True}
            except Exception as e:
                return {"success": False, "error": str(e)}

    def focus(self, app_id: str) -> Dict[str, Any]:
        """Donne le focus à la fenêtre X11 de l'application."""
        with self._lock:
            app = self.registry.get(app_id)
            if not app:
                return {"success": False, "error": f"Application '{app_id}' introuvable"}
            win_id = app.get("window_id")
            if not win_id:
                win_id = ApplicationHealth.find_window_id_for_pid(app.get("pid"))
            if not win_id:
                return {"success": False, "error": "Aucune fenêtre X11 détectée pour cette application"}

            try:
                if shutil.which("xdotool"):
                    subprocess.run(["xdotool", "windowactivate", str(win_id)], check=True, timeout=1.0)
                    return {"success": True, "focused_window": win_id}
                elif shutil.which("wmctrl"):
                    subprocess.run(["wmctrl", "-ia", str(win_id)], check=True, timeout=1.0)
                    return {"success": True, "focused_window": win_id}
                return {"success": False, "error": "xdotool ou wmctrl non disponible"}
            except Exception as e:
                return {"success": False, "error": str(e)}

    def status(self, app_id: str) -> Dict[str, Any]:
        """Retourne le bilan de santé probe live pour une application."""
        with self._lock:
            app = self.registry.get(app_id)
            if not app:
                return {"success": False, "error": "Application introuvable"}
            probe_res = ApplicationHealth.probe(app)
            return {"success": True, "application": app, "health": probe_res}


# ─── SINGLETON GLOBAL MANAGER ────────────────────────────────────────────────

_app_manager_instance: Optional[ApplicationController] = None
_app_lock = threading.Lock()


def get_application_manager() -> ApplicationController:
    global _app_manager_instance
    with _app_lock:
        if _app_manager_instance is None:
            reg = ApplicationRegistry()
            _app_manager_instance = ApplicationController(reg)
            # Pré-découverte au chargement
            reg.discover_all()
        return _app_manager_instance
