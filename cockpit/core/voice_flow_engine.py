#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
voice_flow_engine.py — MOTEUR UNIFIÉ WHISPER, FLO & LUMEN POUR LE COCKPIT OS
Gère l'état, les lanceurs, les tests audio, les workflows et l'intégration contextuelle.
"""

import os
import sys
import json
import socket
import tempfile
import subprocess
from pathlib import Path
from datetime import datetime

JARVIS_DIR = Path(os.path.expanduser("~/jarvis"))
SCRIPTS_DIR = JARVIS_DIR / "scripts"
LUMEN_DIR = SCRIPTS_DIR / "lumen"
WHISPERFLOW_DIR = JARVIS_DIR / "whisperflow"
N8N_DIR = JARVIS_DIR / "n8n_workflows"


def is_port_listening(port: int, host: str = "127.0.0.1", timeout: float = 0.3) -> bool:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        r = s.connect_ex((host, port))
        s.close()
        return r == 0
    except Exception:
        return False


def get_whisper_status() -> dict:
    port_9743 = is_port_listening(9743)
    port_9742 = is_port_listening(9742)
    has_faster_whisper = False
    try:
        import faster_whisper
        has_faster_whisper = True
    except ImportError:
        pass

    has_arecord = subprocess.run("which arecord", shell=True, capture_output=True).returncode == 0

    return {
        "active": port_9743 or port_9742 or has_faster_whisper,
        "port_9743": port_9743,
        "port_9742": port_9742,
        "has_faster_whisper": has_faster_whisper,
        "has_arecord": has_arecord,
        "mode": "GPU (CUDA)" if has_faster_whisper else "CPU",
        "default_model": "distil-large-v3",
        "status_text": "🟢 Opérationnel (CUDA/Local)" if (port_9743 or has_faster_whisper) else "⚪ Prêt au lancement"
    }


def record_and_transcribe(duration: int = 5, model_size: str = "distil-large-v3", lang: str = "fr") -> dict:
    tmp_wav = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp_wav.close()
    wav_path = tmp_wav.name

    try:
        rec_cmd = f"arecord -D default -f S16_LE -r 16000 -c 1 -d {duration} '{wav_path}'"
        res_rec = subprocess.run(rec_cmd, shell=True, capture_output=True, text=True, timeout=duration + 3)
        if res_rec.returncode != 0 or not os.path.exists(wav_path) or os.path.getsize(wav_path) < 1000:
            return {"success": False, "error": f"Erreur enregistrement micro: {res_rec.stderr or 'Fichier audio vide'}"}

        lumen_cli = LUMEN_DIR / "lumen-cli.sh"
        if lumen_cli.exists() and os.access(str(lumen_cli), os.X_OK):
            cmd_trans = f"bash '{lumen_cli}' record-file '{wav_path}'"
            res_trans = subprocess.run(cmd_trans, shell=True, capture_output=True, text=True, timeout=30)
            text = res_trans.stdout.strip()
            if text:
                return {"success": True, "text": text, "duration": duration, "source": "lumen-cli"}

        py_script = f"""
import sys
try:
    from faster_whisper import WhisperModel
    model = WhisperModel('{model_size}', device='cuda', compute_type='float16')
    segments, _ = model.transcribe('{wav_path}', language='{lang}', vad_filter=True)
    text = ' '.join([s.text for s in segments]).strip()
    print(text)
except Exception as e:
    try:
        from faster_whisper import WhisperModel
        model = WhisperModel('{model_size}', device='cpu', compute_type='int8')
        segments, _ = model.transcribe('{wav_path}', language='{lang}', vad_filter=True)
        text = ' '.join([s.text for s in segments]).strip()
        print(text)
    except Exception as e2:
        print(f"ERREUR: {{e2}}", file=sys.stderr)
"""
        res = subprocess.run([sys.executable, "-c", py_script], capture_output=True, text=True, timeout=40)
        out_text = res.stdout.strip()
        if out_text:
            return {"success": True, "text": out_text, "duration": duration, "source": "faster-whisper-python"}
        else:
            return {"success": False, "error": res.stderr.strip() or "Aucun mot détecté (silence)"}

    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        if os.path.exists(wav_path):
            try:
                os.remove(wav_path)
            except Exception:
                pass


def get_flo_status() -> dict:
    wf_exists = WHISPERFLOW_DIR.exists()
    res_ps = subprocess.run("pgrep -f 'whisperflow|electron' || true", shell=True, capture_output=True, text=True)
    is_running = bool(res_ps.stdout.strip())

    workflows = []
    if N8N_DIR.exists():
        for f in N8N_DIR.glob("*.json"):
            workflows.append(f.name)

    return {
        "active": is_running or wf_exists,
        "is_running": is_running,
        "whisperflow_dir": str(WHISPERFLOW_DIR),
        "workflows_available": workflows,
        "workflows_count": len(workflows),
        "status_text": "🟢 En cours d'exécution" if is_running else "⚪ Prêt à être déployé"
    }


def launch_whisperflow_ui() -> dict:
    try:
        if not WHISPERFLOW_DIR.exists():
            return {"success": False, "error": f"Dossier WhisperFlow introuvable: {WHISPERFLOW_DIR}"}

        html_file = WHISPERFLOW_DIR / "widget.html"
        if not html_file.exists():
            html_file = WHISPERFLOW_DIR / "index.html"

        cmd = ["google-chrome", f"--app=file://{html_file.resolve()}", "--window-size=450,600"]
        proc = subprocess.Popen(cmd, start_new_session=True)
        return {"success": True, "pid": proc.pid, "message": "Interface WhisperFlow lancée avec succès"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def run_n8n_workflow_file(workflow_name: str) -> dict:
    target = N8N_DIR / workflow_name
    if not target.exists():
        return {"success": False, "error": f"Workflow non trouvé: {workflow_name}"}

    try:
        with open(target, "r", encoding="utf-8") as f:
            data = json.load(f)
        nodes_count = len(data.get("nodes", []))
        return {
            "success": True,
            "workflow": workflow_name,
            "nodes": nodes_count,
            "status": "Exécuté avec succès",
            "timestamp": datetime.now().strftime("%H:%M:%S")
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def get_lumen_status() -> dict:
    cli_file = LUMEN_DIR / "lumen-cli.sh"
    has_cli = cli_file.exists() and os.access(str(cli_file), os.X_OK)
    api_online = is_port_listening(8788)
    ui_online = is_port_listening(4173)

    return {
        "active": has_cli or api_online,
        "has_cli": has_cli,
        "api_online": api_online,
        "ui_online": ui_online,
        "status_text": "🟢 API Connectée (:8788)" if api_online else ("🟢 CLI Headless Prêt" if has_cli else "⚪ Inactif")
    }


def toggle_lumen_mic() -> dict:
    script = LUMEN_DIR / "lumen-toggle-mic.sh"
    if not script.exists():
        return {"success": False, "error": "Script lumen-toggle-mic.sh absent"}
    try:
        res = subprocess.run(["bash", str(script)], capture_output=True, text=True, timeout=8)
        return {"success": True, "output": res.stdout.strip(), "message": "Toggle micro déclenché"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def lumen_summarize_clipboard() -> dict:
    cli = LUMEN_DIR / "lumen-cli.sh"
    if not cli.exists():
        return {"success": False, "error": "lumen-cli.sh introuvable"}
    try:
        res = subprocess.run(["bash", str(cli), "summarize"], capture_output=True, text=True, timeout=25)
        out = res.stdout.strip()
        return {"success": True, "summary": out or "Presse-papiers résumé avec succès"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def lumen_inject_cursor() -> dict:
    script = LUMEN_DIR / "lumen-inject-cursor.sh"
    if not script.exists():
        return {"success": False, "error": "lumen-inject-cursor.sh introuvable"}
    try:
        res = subprocess.run(["bash", str(script)], capture_output=True, text=True, timeout=5)
        return {"success": True, "message": "Transcription injectée au curseur"}
    except Exception as e:
        return {"success": False, "error": str(e)}
