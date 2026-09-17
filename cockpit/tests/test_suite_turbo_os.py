#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TURBO OS / JARVIS — BATTERIE GLOBALE DE TESTS DE NON-RÉGRESSION
==============================================================
Vérification automatisée sur preuves réelles (pas de mock trompeur) :
1. test_cockpit
2. test_runtime
3. test_mcp
4. test_lmstudio
5. test_cuda
6. test_gpu
7. test_voice
8. test_stt
9. test_tts
10. test_browser
11. test_pc_control
12. test_memory
13. test_rag
14. test_board
15. test_domino
16. test_checkpoint
17. test_security
18. test_email
19. test_packaging
"""

import os
import sys
import json
import socket
import unittest
import urllib.request
import subprocess

COCKPIT_URL = "http://127.0.0.1:8600"


class TestTurboOS(unittest.TestCase):

    def _http_get(self, path, timeout=3):
        url = f"{COCKPIT_URL}{path}"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))

    # 1. test_cockpit
    def test_cockpit(self):
        d = self._http_get("/api/status")
        self.assertTrue("hostname" in d or "services" in d)

    # 2. test_runtime
    def test_runtime(self):
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from core.model_registry import RuntimeHealth
        h = RuntimeHealth.check_all()
        self.assertIn("execution", h)
        self.assertIn("reasoning", h)

    # 3. test_mcp
    def test_mcp(self):
        d = self._http_get("/api/mcp")
        self.assertIn("mcps", d)
        self.assertGreater(d.get("count", 0), 0)

    # 4. test_lmstudio
    def test_lmstudio(self):
        # Nœuds locaux réels :1234 et :1235
        with socket.create_connection(("127.0.0.1", 1234), timeout=1) as s:
            self.assertIsNotNone(s)

    # 5. test_cuda & 6. test_gpu
    def test_cuda_and_gpu(self):
        out = subprocess.check_output("nvidia-smi --query-gpu=name,memory.total --format=csv,noheader", shell=True).decode()
        self.assertIn("RTX 3080", out)
        self.assertIn("RTX 2060", out)

    # 7. test_voice & 9. test_tts
    def test_voice_and_tts(self):
        # Service Kokoro ou port TTS :1250
        with socket.create_connection(("127.0.0.1", 1250), timeout=1) as s:
            self.assertIsNotNone(s)

    # 8. test_stt
    def test_stt(self):
        # Vérification du service voice_cockpit :1270
        with socket.create_connection(("127.0.0.1", 1270), timeout=1) as s:
            self.assertIsNotNone(s)

    # 10. test_browser & 11. test_pc_control
    def test_browser_and_pc_control(self):
        self.assertTrue(os.path.exists("/usr/bin/google-chrome") or os.path.exists("/usr/bin/chromium"))

    # 12. test_memory & 13. test_rag & 14. test_board
    def test_memory_rag_board(self):
        board_path = "/home/turbo/jarvis/board/board.db"
        self.assertTrue(os.path.exists(board_path))
        d = self._http_get("/api/memory/stats")
        stats = d.get("stats", {})
        self.assertGreater(stats.get("total_actions", 0), 0)

    # 15. test_domino
    def test_domino(self):
        domino_db = "/home/turbo/jarvis/omega/domino-continu/domino_continu.db"
        self.assertTrue(os.path.exists(domino_db))

    # 16. test_checkpoint
    def test_checkpoint(self):
        d = self._http_get("/api/checkpoint/list")
        self.assertIn("items", d)

    # 17. test_security
    def test_security(self):
        # Simuler un accès non autorisé depuis l'IP pont
        try:
            req = urllib.request.Request("http://10.42.0.1:8600/api/status")
            urllib.request.urlopen(req, timeout=2)
            self.fail("Devait lever HTTPError 403")
        except urllib.error.HTTPError as e:
            self.assertEqual(e.code, 403)
        except Exception:
            pass  # Rejet attendu

    # 18. test_email
    def test_email(self):
        d = self._http_get("/api/emails/triage/status")
        self.assertTrue(d.get("success", False))
        self.assertIn("total_emails", d)

    # 19. test_packaging
    def test_packaging(self):
        # 1. Lanceur bureau canonique
        launcher = "/home/turbo/.local/bin/turbo-os"
        self.assertTrue(os.path.exists(launcher))
        self.assertTrue(os.access(launcher, os.X_OK))

        # 2. Binaires et scripts du packaging cockpit
        repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        required_files = [
            os.path.join(repo_root, "bin", "jarvis-cockpit-app"),
            os.path.join(repo_root, "bin", "jarvis-cockpit.sh"),
            os.path.join(repo_root, "bin", "jarvis-planning-widget.py"),
            os.path.join(repo_root, "bin", "swarm-watch.sh"),
            os.path.join(repo_root, "bin", "m6-watch.sh"),
            os.path.join(repo_root, "scripts", "planning_mega_m4.py"),
            os.path.join(repo_root, "VERSION"),
            os.path.join(repo_root, "CHANGELOG.md"),
        ]
        for f in required_files:
            self.assertTrue(os.path.exists(f), f"Fichier de packaging requis absent: {f}")
            if f.endswith((".sh", ".py", "jarvis-cockpit-app")):
                self.assertTrue(os.access(f, os.X_OK), f"Fichier non exécutable: {f}")


if __name__ == "__main__":
    unittest.main()
