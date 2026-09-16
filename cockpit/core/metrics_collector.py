#!/usr/bin/env python3
"""
metrics_collector.py — Collecte métriques système JARVIS en temps réel
Mesures : GPU (VRAM, util, temp), RAM, CPU, LM Studio (modèles, tok/s), tunnels SSH, Postgres
"""
import subprocess
import json
import datetime
import os
import threading
import time
import urllib.request
import urllib.error

METRICS_CACHE = "/home/turbo/jarvis/data/metrics_cache.json"
ALERTS_FILE = "/home/turbo/jarvis/data/alerts.jsonl"
METRICS_HISTORY = "/home/turbo/jarvis/data/metrics_history.jsonl"

SEUILS = {
    "gpu_temp_warning": 80,     # °C
    "gpu_temp_critical": 90,
    "gpu_vram_warning": 85,     # %
    "gpu_util_warning": 95,     # %
    "ram_warning": 85,          # %
    "lms_ttft_warning": 500,    # ms
}

TUNNELS = [
    {"port": 11500, "service": "Ollama Rémi",     "path": "/api/tags"},
    {"port": 8601,  "service": "Cockpit2 Rémi",   "path": "/"},
    {"port": 8899,  "service": "Planning Widget",  "path": "/data"},
    {"port": 5001,  "service": "Board OS",         "path": "/api/state"},
]


# ─── GPU ───────────────────────────────────────────────────────────────────────

def collecter_gpu() -> list:
    """nvidia-smi → [{index, name, vram_used_mb, vram_total_mb, vram_pct, util_pct, temp_c}]"""
    try:
        out = subprocess.check_output([
            "nvidia-smi",
            "--query-gpu=index,name,memory.used,memory.total,utilization.gpu,temperature.gpu",
            "--format=csv,noheader,nounits"
        ], text=True, timeout=4)
        gpus = []
        for line in out.strip().splitlines():
            p = [x.strip() for x in line.split(",")]
            if len(p) >= 6:
                used = int(p[2])
                total = int(p[3])
                gpus.append({
                    "index": int(p[0]),
                    "name": p[1],
                    "vram_used_mb": used,
                    "vram_total_mb": total,
                    "vram_pct": round(used / max(1, total) * 100, 1),
                    "util_pct": int(p[4]),
                    "temp_c": int(p[5]),
                })
        return gpus
    except Exception as e:
        return [{"error": str(e)}]


# ─── RAM ───────────────────────────────────────────────────────────────────────

def collecter_ram() -> dict:
    """Lire /proc/meminfo → {total_gb, used_gb, available_gb, used_pct}"""
    try:
        info = {}
        with open("/proc/meminfo") as f:
            for line in f:
                parts = line.split()
                if len(parts) >= 2:
                    info[parts[0].rstrip(":")] = int(parts[1])
        total = info.get("MemTotal", 1)
        avail = info.get("MemAvailable", 0)
        used = total - avail
        return {
            "total_gb": round(total / 1024 / 1024, 2),
            "used_gb": round(used / 1024 / 1024, 2),
            "available_gb": round(avail / 1024 / 1024, 2),
            "used_pct": round(used / max(1, total) * 100, 1),
        }
    except Exception as e:
        return {"error": str(e)}


# ─── CPU ───────────────────────────────────────────────────────────────────────

def collecter_cpu() -> dict:
    """Lire /proc/stat (2 lectures 0.5s) → {util_pct, load_1m, load_5m}"""
    try:
        def _lire_cpu():
            with open("/proc/stat") as f:
                line = f.readline()
            vals = list(map(int, line.split()[1:]))
            idle = vals[3]
            total = sum(vals)
            return idle, total

        idle1, total1 = _lire_cpu()
        time.sleep(0.5)
        idle2, total2 = _lire_cpu()
        delta_idle = idle2 - idle1
        delta_total = total2 - total1
        util = round((1 - delta_idle / max(1, delta_total)) * 100, 1)

        load = os.getloadavg()
        return {
            "util_pct": util,
            "load_1m": round(load[0], 2),
            "load_5m": round(load[1], 2),
        }
    except Exception as e:
        return {"error": str(e)}


# ─── LM Studio ─────────────────────────────────────────────────────────────────

def collecter_lms() -> dict:
    """GET http://127.0.0.1:1234/v1/models → {status, modeles_count, modeles: [...]}"""
    try:
        req = urllib.request.Request(
            "http://127.0.0.1:1234/v1/models",
            headers={"User-Agent": "JarvisMetrics/1.0"}
        )
        with urllib.request.urlopen(req, timeout=2.5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        modeles = [m.get("id", "") for m in data.get("data", [])]
        llms = [m for m in data.get("data", []) if m.get("type", "llm") == "llm" or "id" in m]
        charges = [m.get("id") for m in llms if m.get("state") == "loaded" or m.get("state") is None or "owned_by" in m]
        return {
            "status": "online",
            "modeles_count": len(modeles),
            "modeles": modeles[:15],
            "llms_charges": charges,
        }
    except Exception as e:
        return {"status": "offline", "error": str(e), "modeles_count": 0, "modeles": [], "llms_charges": []}


# ─── Tunnels ───────────────────────────────────────────────────────────────────

def collecter_tunnels() -> list:
    """Vérifie connectivité des 4 ports tunnels → [{port, service, ok, latency_ms}]"""
    resultats = []
    for t in TUNNELS:
        port = t["port"]
        path = t.get("path", "/")
        t0 = time.perf_counter()
        ok = False
        try:
            req = urllib.request.Request(
                f"http://127.0.0.1:{port}{path}",
                headers={"User-Agent": "JarvisMetrics/1.0"}
            )
            with urllib.request.urlopen(req, timeout=1.5):
                ok = True
        except Exception:
            pass
        latency = round((time.perf_counter() - t0) * 1000, 1)
        resultats.append({
            "port": port,
            "service": t["service"],
            "ok": ok,
            "latency_ms": latency if ok else None,
        })
    return resultats


# ─── Alertes ───────────────────────────────────────────────────────────────────

def verifier_alertes(metrics: dict) -> list:
    """Compare métriques aux SEUILS, retourne liste d'alertes [{niveau, message, valeur, ts}]"""
    alertes = []
    ts = datetime.datetime.now().isoformat()

    # GPU
    for gpu in metrics.get("gpu", []):
        if gpu.get("error"):
            continue
        idx = gpu.get("index", "?")
        temp = gpu.get("temp_c", 0)
        vram_pct = gpu.get("vram_pct", 0)
        util = gpu.get("util_pct", 0)

        if temp >= SEUILS["gpu_temp_critical"]:
            alertes.append({"niveau": "critical", "ts": ts,
                            "message": f"GPU{idx} température critique : {temp}°C", "valeur": temp})
        elif temp >= SEUILS["gpu_temp_warning"]:
            alertes.append({"niveau": "warning", "ts": ts,
                            "message": f"GPU{idx} température élevée : {temp}°C", "valeur": temp})

        if vram_pct >= SEUILS["gpu_vram_warning"]:
            alertes.append({"niveau": "warning", "ts": ts,
                            "message": f"GPU{idx} VRAM saturée : {vram_pct}%", "valeur": vram_pct})

        if util >= SEUILS["gpu_util_warning"]:
            alertes.append({"niveau": "warning", "ts": ts,
                            "message": f"GPU{idx} utilisation maximale : {util}%", "valeur": util})

    # RAM
    ram = metrics.get("ram", {})
    if ram.get("used_pct", 0) >= SEUILS["ram_warning"]:
        alertes.append({"niveau": "warning", "ts": ts,
                        "message": f"RAM saturée : {ram['used_pct']}%", "valeur": ram["used_pct"]})

    # LM Studio
    lms = metrics.get("lms", {})
    if lms.get("status") == "offline":
        alertes.append({"niveau": "warning", "ts": ts,
                        "message": "LM Studio hors ligne (port 1234)", "valeur": None})

    # Tunnels
    for t in metrics.get("tunnels", []):
        if not t.get("ok"):
            alertes.append({"niveau": "warning", "ts": ts,
                            "message": f"Tunnel KO : {t['service']} (port {t['port']})", "valeur": None})

    return alertes


def sauver_alertes(alertes: list):
    """Append alertes dans ALERTS_FILE."""
    if not alertes:
        return
    os.makedirs(os.path.dirname(ALERTS_FILE), exist_ok=True)
    with open(ALERTS_FILE, "a") as f:
        for a in alertes:
            f.write(json.dumps(a, ensure_ascii=False) + "\n")


def lire_alertes(n: int = 20) -> list:
    """Lit les N dernières alertes depuis ALERTS_FILE."""
    if not os.path.exists(ALERTS_FILE):
        return []
    try:
        with open(ALERTS_FILE, "r") as f:
            lignes = f.readlines()
        return [json.loads(l) for l in lignes[-n:] if l.strip()]
    except Exception:
        return []


# ─── Snapshot complet ──────────────────────────────────────────────────────────

def snapshot() -> dict:
    """Tout en 1 : GPU + RAM + CPU + LMS + tunnels + alertes (threads simultanés)."""
    resultats = {}
    lock = threading.Lock()

    def _run(key, fn, *args):
        val = fn(*args)
        with lock:
            resultats[key] = val

    threads = [
        threading.Thread(target=_run, args=("gpu", collecter_gpu)),
        threading.Thread(target=_run, args=("ram", collecter_ram)),
        threading.Thread(target=_run, args=("cpu", collecter_cpu)),
        threading.Thread(target=_run, args=("lms", collecter_lms)),
        threading.Thread(target=_run, args=("tunnels", collecter_tunnels)),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=5)

    metrics = {
        "ts": datetime.datetime.now().isoformat(),
        "gpu": resultats.get("gpu", []),
        "ram": resultats.get("ram", {}),
        "cpu": resultats.get("cpu", {}),
        "lms": resultats.get("lms", {}),
        "tunnels": resultats.get("tunnels", []),
    }
    alertes = verifier_alertes(metrics)
    metrics["alertes"] = alertes
    if alertes:
        sauver_alertes(alertes)
    sauver_cache(metrics)
    return metrics


# ─── Cache ─────────────────────────────────────────────────────────────────────

def sauver_cache(data: dict):
    """Sauve dans METRICS_CACHE."""
    os.makedirs(os.path.dirname(METRICS_CACHE), exist_ok=True)
    try:
        with open(METRICS_CACHE, "w") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def lire_cache() -> dict:
    """Lit METRICS_CACHE, retourne {} si inexistant."""
    if not os.path.exists(METRICS_CACHE):
        return {}
    try:
        with open(METRICS_CACHE, "r") as f:
            return json.load(f)
    except Exception:
        return {}


def sauver_historique(data: dict):
    """Append dans metrics_history.jsonl."""
    os.makedirs(os.path.dirname(METRICS_HISTORY), exist_ok=True)
    try:
        with open(METRICS_HISTORY, "a") as f:
            f.write(json.dumps(data, ensure_ascii=False) + "\n")
    except Exception:
        pass


def lire_historique(n: int = 50) -> list:
    """Lit les N dernières entrées de metrics_history.jsonl."""
    if not os.path.exists(METRICS_HISTORY):
        return []
    try:
        with open(METRICS_HISTORY, "r") as f:
            lignes = f.readlines()
        return [json.loads(l) for l in lignes[-n:] if l.strip()]
    except Exception:
        return []
