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

def is_port_open(host: str, port: int, timeout: float = 0.25) -> bool:
    """Vérifie l'accessibilité d'un port TCP avec un timeout strict."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        s.connect((host, port))
        s.close()
        return True
    except Exception:
        return False

def get_vram_info() -> dict:
    """Récupère les métriques GPU NVIDIA (support mono et multi-GPU)."""
    try:
        r = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.used,memory.total,temperature.gpu,utilization.gpu", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=1
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
                # Garde thermique — doctrine rig "mining" (Notion ⛏️, règle #3) :
                # la GTX 1660 SUPER n'a plus de ventilateur (82-91 °C à 1 % d'usage).
                # Prendre le max ferait sonner l'alerte en permanence à cause de cette
                # carte oisive. On l'exclut du garde-fou (sans masquer son détail dans
                # `gpus`), et on retombe sur la médiane si la liste devenait vide.
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
                return {
                    "name": name_summary,
                    "used": tot_used,
                    "total": tot_total,
                    "temp": max_temp,
                    "util": avg_util,
                    "available": True,
                    "count": len(gpus),
                    "gpus": gpus
                }
    except Exception:
        pass
    return {"name": "Aucun GPU NVIDIA", "used": 0, "total": 0, "temp": 0, "util": 0, "available": False, "count": 0, "gpus": []}

def get_ram_info() -> dict:
    """Lit /proc/meminfo pour des métriques précises sans spawn de process."""
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
    """CPU usage, load averages et températures réelles."""
    try:
        with open("/proc/loadavg") as f:
            loads = f.read().strip().split()[:3]
    except Exception:
        loads = ["0.00", "0.00", "0.00"]

    temp = 0
    try:
        sensors_out = subprocess.getoutput("sensors 2>/dev/null | grep -m1 -oP 'Package id 0:\\s+\\+\\K[0-9.]+'").strip()
        if sensors_out:
            temp = float(sensors_out)
        else:
            temp_raw = subprocess.getoutput("cat /sys/class/thermal/thermal_zone*/temp 2>/dev/null | sort -rn | head -1").strip()
            if temp_raw.isdigit():
                temp = round(int(temp_raw) / 1000, 1)
    except Exception:
        pass

    # Swap & zram
    zram_pct = 0
    zram_used_mb = 0
    try:
        with open("/proc/swaps") as f:
            for line in f:
                if "zram" in line:
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
    """Espace disque sur partitions maîtresses."""
    partitions = {}
    for mount_point in ["/", "/storage", "/media/pamerys/JARVIS-M11"]:
        if os.path.exists(mount_point):
            try:
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
    """Sonde l'état du nœud M6 (Tour 4 GPU reliée par câble direct USB-C ASIX 10.42.0.230)."""
    online = False
    latency_ms = 0.0
    loaded_models = []
    available_models = []
    
    if is_port_open(M6_HOST, M6_PORT, timeout=0.3):
        online = True
        try:
            t0 = time.time()
            req = urllib.request.Request(f"{M6_URL}/api/v0/models")
            with urllib.request.urlopen(req, timeout=1.5) as resp:
                latency_ms = round((time.time() - t0) * 1000, 1)
                data = json.loads(resp.read().decode())
                for m in data.get("data", []):
                    m_id = m.get("id", "")
                    available_models.append(m_id)
                    if m.get("state") == "loaded":
                        loaded_models.append(m_id)
        except Exception:
            pass

    return {
        "host": M6_HOST,
        "port": M6_PORT,
        "online": online,
        "latency_ms": latency_ms,
        "loaded_models": loaded_models,
        "available_models": available_models,
        "direct_link": "Lien USB-C ASIX 10.42.0.230 (1.4 ms)"
    }

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
