#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JARVIS COCKPIT — TELEMETRY ENGINE
High-performance non-blocking telemetry probe for M4 hardware, M6 GPU cluster, Swarm, and microservices.
"""

import os
import socket
import subprocess
import json
import time
import urllib.request
from .config import (
    M6_HOST, M6_PORT, M6_URL, OLLAMA_URL, ORGANES, MACHINE_NAME
)
from .platform_compat import (
    IS_WINDOWS, run_cmd, which, local_listening_ports, tailscale_via_socks,
    ram_info as _compat_ram_info, cpu_info as _compat_cpu_info,
    storage_mount_points, disk_usage as _compat_disk_usage,
)

_LOOPBACK_HOSTS = ("127.0.0.1", "localhost", "::1")

_VRAM_CACHE = None
_VRAM_CACHE_TIME = 0.0
_VRAM_TTL = 3.0  # Cache 3s réactif adapté au Core i5 4 cœurs

_M6_CACHE = None
_M6_CACHE_TIME = 0.0
_M6_TTL = 5.0   # Cache 5s réactif pour LM Studio GPU local / tether

def is_port_open(host: str, port: int, timeout: float = None) -> bool:
    """Vérifie l'accessibilité d'un port TCP avec un timeout strict et adapté."""
    if timeout is None:
        timeout = 0.02 if host in _LOOPBACK_HOSTS else 0.5
    try:
        if IS_WINDOWS and host in _LOOPBACK_HOSTS:
            # Windows : un port loopback FERMÉ n'est refusé qu'après ~2 s (le
            # connect() brûle tout son timeout). On lit la table LISTEN via
            # psutil (2 ms, cache 1 s) ; repli connect() si psutil est absent.
            ports = local_listening_ports()
            if ports:
                return int(port) in ports
        if host.startswith("100.") and tailscale_via_socks():
            # Route les sondes Tailscale via le proxy SOCKS5 local (127.0.0.1:1055)
            # RTT Tailscale peut être de 100-300ms, on assure un timeout adapté (min 1.2s)
            timeout = max(timeout or 0, 1.2)
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(timeout)
            s.connect(("127.0.0.1", 1055))
            s.sendall(b"\x05\x01\x00")
            if s.recv(2) != b"\x05\x00":
                s.close()
                return False
            ip_parts = [int(x) for x in host.split(".")]
            s.sendall(b"\x05\x01\x00\x01" + bytes(ip_parts) + port.to_bytes(2, "big"))
            resp = s.recv(10)
            s.close()
            return len(resp) >= 4 and resp[1] == 0
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        s.connect((host, port))
        s.close()
        return True
    except Exception:
        return False

def get_vram_info(force: bool = False) -> dict:
    """Récupère les métriques GPU NVIDIA (avec cache TTL pour épargner le CPU 2 cœurs)."""
    global _VRAM_CACHE, _VRAM_CACHE_TIME
    now = time.time()
    if not force and _VRAM_CACHE is not None and (now - _VRAM_CACHE_TIME) < _VRAM_TTL:
        return _VRAM_CACHE

    try:
        # run_cmd : CREATE_NO_WINDOW sous Windows (pas de flash de console toutes
        # les 3 s sous pythonw), utf-8, ne lève jamais (127 si nvidia-smi absent).
        smi = which("nvidia-smi") or "nvidia-smi"
        r = run_cmd(
            [smi, "--query-gpu=name,memory.used,memory.total,temperature.gpu,utilization.gpu", "--format=csv,noheader,nounits"],
            timeout=1.5
        )
        if r.returncode == 0 and r.stdout.strip():
            gpus = []
            for line in r.stdout.strip().splitlines():
                parts = [p.strip() for p in line.split(",") if p.strip()]
                if len(parts) >= 5:
                    try:
                        gpus.append({
                            "name": parts[0],
                            "used": int(parts[1]),
                            "total": int(parts[2]),
                            "temp": int(parts[3]),
                            "util": int(parts[4]),
                        })
                    except ValueError:
                        continue
            if gpus:
                tot_used = sum(g["used"] for g in gpus)
                tot_total = sum(g["total"] for g in gpus)
                temps_garde = [g["temp"] for g in gpus if "1660" not in g["name"]]
                if not temps_garde:
                    temps_garde = sorted(g["temp"] for g in gpus)[len(gpus) // 2:len(gpus) // 2 + 1]
                max_temp = max(temps_garde)
                avg_util = round(sum(g["util"] for g in gpus) / len(gpus))
                if len(gpus) == 1:
                    name_summary = gpus[0]["name"]
                else:
                    short_names = [g["name"].replace("NVIDIA GeForce ", "").replace("NVIDIA ", "") for g in gpus]
                    name_summary = f"{len(gpus)}x GPUs ({', '.join(short_names)})"
                res = {
                    "name": name_summary,
                    "used": tot_used,
                    "total": tot_total,
                    "temp": max_temp,
                    "util": avg_util,
                    "available": True,
                    "count": len(gpus),
                    "gpus": gpus
                }
                _VRAM_CACHE = res
                _VRAM_CACHE_TIME = now
                return res
    except Exception:
        pass
    fallback = {"name": "Aucun GPU NVIDIA", "used": 0, "total": 0, "temp": 0, "util": 0, "available": False, "count": 0, "gpus": []}
    if _VRAM_CACHE is None:
        _VRAM_CACHE = fallback
        _VRAM_CACHE_TIME = now
    return _VRAM_CACHE

def get_ram_info() -> dict:
    """Lit /proc/meminfo pour des métriques précises sans spawn de process.

    Sous Windows (pas de /proc) : psutil.virtual_memory() via platform_compat,
    afin d'afficher la RAM réelle et non un 16 Go fictif."""
    if IS_WINDOWS:
        info = _compat_ram_info()
        if not info.get("error"):
            return {k: info[k] for k in ("total_mb", "used_mb", "avail_mb", "percent", "total_gb", "used_gb")}
        return {"total_mb": 0, "used_mb": 0, "avail_mb": 0, "percent": 0, "total_gb": 0.0, "used_gb": 0.0}
    try:
        with open("/proc/meminfo") as f:
            lines = f.readlines()
            tot = int(lines[0].split()[1]) / 1024  # Mo
            free = int(lines[1].split()[1]) / 1024
            avail = int(lines[2].split()[1]) / 1024
            used = tot - avail
            pct = round((used / tot) * 100, 1) if tot > 0 else 0
            return {
                "total_mb": int(tot),
                "used_mb": int(used),
                "avail_mb": int(avail),
                "percent": pct,
                "total_gb": round(tot / 1024, 1),
                "used_gb": round(used / 1024, 1)
            }
    except Exception:
        return {"total_mb": 16384, "used_mb": 0, "avail_mb": 16384, "percent": 0, "total_gb": 16.0, "used_gb": 0.0}

def get_cpu_info() -> dict:
    """CPU usage, load averages et températures réelles (100% lecture directe, 0 sous-processus).

    Sous Windows : psutil (loadavg émulé, pagefile en guise de zram), temp_c=0.0
    (aucune sonde thermique standard sans pilote tiers)."""
    if IS_WINDOWS:
        info = _compat_cpu_info()
        return {k: info[k] for k in ("load_1m", "load_5m", "load_15m", "temp_c", "zram_percent", "zram_used_mb")}
    try:
        with open("/proc/loadavg") as f:
            loads = f.read().strip().split()[:3]
    except Exception:
        loads = ["0.00", "0.00", "0.00"]

    temp = 0.0
    try:
        import glob
        temps = []
        for p in glob.glob("/sys/class/thermal/thermal_zone*/temp"):
            try:
                with open(p, "r") as tf:
                    t_val = tf.read().strip()
                    if t_val.isdigit():
                        temps.append(round(int(t_val) / 1000.0, 1))
            except Exception:
                pass
        if temps:
            temp = max(temps)
    except Exception:
        pass

    # Swap & zram
    zram_pct = 0
    zram_used_mb = 0
    try:
        with open("/proc/swaps") as f:
            for line in f:
                if "zram" in line or "partition" in line:
                    parts = line.split()
                    tot_kb = int(parts[2])
                    used_kb = int(parts[3])
                    zram_used_mb = round(used_kb / 1024, 1)
                    if tot_kb > 0:
                        zram_pct = round((used_kb / tot_kb) * 100, 1)
    except Exception:
        pass

    return {
        "load_1m": loads[0],
        "load_5m": loads[1],
        "load_15m": loads[2],
        "temp_c": temp,
        "zram_percent": zram_pct,
        "zram_used_mb": zram_used_mb
    }

def get_storage_info() -> dict:
    """Espace disque sur partitions maîtresses (système + SSDs M1 & M6)."""
    partitions = {}
    # Linux : liste fixe du rig (inchangée) ; Windows : racines des lecteurs fixes (C:\ …).
    for mount_point in storage_mount_points():
        if os.path.exists(mount_point):
            try:
                if IS_WINDOWS:
                    # os.statvfs n'existe pas sous Windows → shutil.disk_usage
                    du = _compat_disk_usage(mount_point)
                    if du is None:
                        raise OSError(f"disk_usage({mount_point}) indisponible")
                    total_gb = round(du[0] / (1024**3), 1)
                    free_gb = round(du[2] / (1024**3), 1)
                else:
                    st = os.statvfs(mount_point)
                    free_gb = round((st.f_bavail * st.f_frsize) / (1024**3), 1)
                    total_gb = round((st.f_blocks * st.f_frsize) / (1024**3), 1)
                used_gb = round(total_gb - free_gb, 1)
                pct = round((used_gb / total_gb) * 100, 1) if total_gb > 0 else 0
                partitions[mount_point] = {
                    "total_gb": total_gb,
                    "used_gb": used_gb,
                    "free_gb": free_gb,
                    "percent": pct,
                    "mounted": True
                }
            except Exception:
                partitions[mount_point] = {"mounted": False}
        else:
            partitions[mount_point] = {"mounted": False}
    return partitions

def get_m6_status() -> dict:
    """Sonde l'état du nœud LM Studio / M6 (probe multi-IP tether 192.168.42.241 + loopback)."""
    global _M6_CACHE, _M6_CACHE_TIME
    now = time.time()
    if _M6_CACHE is not None and (now - _M6_CACHE_TIME) < _M6_TTL:
        return _M6_CACHE

    online = False
    latency_ms = 0.0
    loaded_models = []
    available_models = []
    active_host = M6_HOST
    active_port = M6_PORT

    candidates = [(M6_HOST, M6_PORT), ("192.168.42.241", 1234), ("127.0.0.1", 1234)]
    seen = set()
    for h, p in candidates:
        if (h, p) in seen:
            continue
        seen.add((h, p))
        if is_port_open(h, p, timeout=0.15):
            try:
                t0 = time.time()
                req = urllib.request.Request(f"http://{h}:{p}/api/v0/models")
                with urllib.request.urlopen(req, timeout=1.2) as resp:
                    latency_ms = round((time.time() - t0) * 1000, 1)
                    data = json.loads(resp.read().decode())
                    for m in data.get("data", []):
                        m_id = m.get("id", "")
                        available_models.append(m_id)
                        if m.get("state") == "loaded":
                            loaded_models.append(m_id)
                    online = True
                    active_host = h
                    active_port = p
                    break
            except Exception:
                pass

    res = {
        "host": active_host,
        "port": active_port,
        "online": online,
        "latency_ms": latency_ms,
        "loaded_models": loaded_models,
        "available_models": available_models,
        "direct_link": f"Lien {active_host}:{active_port}"
    }
    _M6_CACHE = res
    _M6_CACHE_TIME = now
    return res

def get_organes_status() -> list[dict]:
    """Sonde en temps réel les 16 organes du système JARVIS."""
    res = []
    for nom, hote, port, role in ORGANES:
        up = is_port_open(hote, port, timeout=0.2)
        res.append({
            "nom": nom,
            "host": hote,
            "port": port,
            "role": role,
            "status": "UP" if up else "DOWN",
            "online": up
        })
    return res

def get_full_telemetry() -> dict:
    """Rassemble l'ensemble des sondes télémétriques."""
    local_metrics = {
        "vram": get_vram_info(),
        "ram": get_ram_info(),
        "cpu": get_cpu_info(),
        "storage": get_storage_info()
    }
    return {
        "timestamp": time.time(),
        "datetime": time.strftime("%Y-%m-%d %H:%M:%S"),
        "machine": MACHINE_NAME,
        "local": local_metrics,
        "m4": local_metrics,
        "m6": get_m6_status(),
        "organes": get_organes_status()
    }
