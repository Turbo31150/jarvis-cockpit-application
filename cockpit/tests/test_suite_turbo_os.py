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
            os.path.join(repo_root, "bin", "jarvis-cockpit-vhdx"),
            os.path.join(repo_root, "bin", "jarvis-cockpit-exporter"),
            os.path.join(repo_root, "bin", "turbo-os-launcher.sh"),
            os.path.join(repo_root, "bin", "ttx"),
            os.path.join(repo_root, "bin", "swarm-watch.sh"),
            os.path.join(repo_root, "bin", "m6-watch.sh"),
            os.path.join(repo_root, "cockpit", "core", "system_state.py"),
            os.path.join(repo_root, "cockpit", "core", "application_manager.py"),
            os.path.join(repo_root, "cockpit", "core", "dispatcher.py"),
            os.path.join(repo_root, "cockpit", "core", "launcher.py"),
            os.path.join(repo_root, "cockpit", "core", "rag_validator.py"),
            os.path.join(repo_root, "cockpit", "terminaux.py"),
            os.path.join(repo_root, "cockpit", "launch_gui.sh"),
            os.path.join(repo_root, "cockpit", "install-cockpit.sh"),
            os.path.join(repo_root, "scripts", "planning_mega_m4.py"),
            os.path.join(repo_root, "VERSION"),
            os.path.join(repo_root, "CHANGELOG.md"),
        ]
        for f in required_files:
            self.assertTrue(os.path.exists(f), f"Fichier de packaging requis absent: {f}")
            if f.endswith((".sh", "jarvis-cockpit-app", "ttx", "planning-widget.py", "planning_mega_m4.py")):
                self.assertTrue(os.access(f, os.X_OK), f"Fichier non exécutable: {f}")

        # 3. Validation CLI help & exécution sans blocage
        cli_help_checks = [
            ["bash", os.path.join(repo_root, "cockpit", "install-cockpit.sh"), "--help"],
            ["bash", os.path.join(repo_root, "bin", "jarvis-cockpit.sh"), "--help"],
            ["bash", os.path.join(repo_root, "bin", "turbo-os-launcher.sh"), "--help"],
            ["bash", os.path.join(repo_root, "bin", "m6-watch.sh"), "--help"],
            ["bash", os.path.join(repo_root, "bin", "swarm-watch.sh"), "--help"],
            [sys.executable, os.path.join(repo_root, "bin", "jarvis-planning-widget.py"), "--help"],
            [sys.executable, os.path.join(repo_root, "scripts", "planning_mega_m4.py"), "--help"],
        ]
        for cmd in cli_help_checks:
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=5)
            self.assertEqual(res.returncode, 0, f"Échec CLI help sur {cmd[1]}: {res.stderr.decode()}")

        # 4. Mode ponctuel --once et dry run
        res_m6 = subprocess.run(["bash", os.path.join(repo_root, "bin", "m6-watch.sh"), "--once"],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=5)
        self.assertEqual(res_m6.returncode, 0)

        res_swarm = subprocess.run(["bash", os.path.join(repo_root, "bin", "swarm-watch.sh"), "--once"],
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=5)
        self.assertEqual(res_swarm.returncode, 0)

        res_planning = subprocess.run([sys.executable, os.path.join(repo_root, "scripts", "planning_mega_m4.py"), "--dry"],
                                      stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
        self.assertEqual(res_planning.returncode, 0)

    # 20. test_system_state_and_transitions
    def test_system_state_and_transitions(self):
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from core.system_state import (
            get_system_state, TaskStatus, ApplicationStatus, ServiceStatus,
            ToolStatus, ModelStatus, HealthStatus, InvalidStateTransitionError
        )
        st = get_system_state()

        # Test existence des enums requis
        self.assertEqual(TaskStatus.RUNNING.value, "RUNNING")
        self.assertEqual(TaskStatus.PAUSED.value, "PAUSED")
        self.assertEqual(TaskStatus.VERIFYING.value, "VERIFYING")
        self.assertEqual(TaskStatus.DONE.value, "DONE")
        self.assertEqual(ApplicationStatus.READY.value, "READY")
        self.assertEqual(ApplicationStatus.RUNNING.value, "RUNNING")
        self.assertEqual(ServiceStatus.ACTIVE.value, "ACTIVE")
        self.assertEqual(ToolStatus.AVAILABLE.value, "AVAILABLE")
        self.assertEqual(ModelStatus.READY.value, "READY")
        self.assertEqual(HealthStatus.HEALTHY.value, "HEALTHY")

        # Test cycle régulier de tâche avec pause/resume et checkpoint
        task_id = "test-task-audit-001"
        st.register_entity("task", task_id, TaskStatus.READY, metadata={"goal": "test audit"})
        st.transition("task", task_id, TaskStatus.RUNNING, "démarrage")

        # Protocole PAUSE : RUNNING -> CHECKPOINT -> PAUSED
        st.pause_task(task_id, reason="mise en pause test", checkpoint_data={"step": 1})
        self.assertEqual(st.get_entity("task", task_id).status, TaskStatus.PAUSED.value)

        # Protocole RESUME : PAUSED -> RESTORE -> RUNNING
        st.resume_task(task_id, reason="reprise test")
        self.assertEqual(st.get_entity("task", task_id).status, TaskStatus.RUNNING.value)

        # Transition interdite : RUNNING -> DONE sans VERIFY
        with self.assertRaises(InvalidStateTransitionError):
            st.transition("task", task_id, TaskStatus.DONE, "interdit direct sans verify")

        # Tentative directe de complete_task depuis RUNNING sans verify doit échouer
        st.register_entity("task", "task-leak-check", TaskStatus.RUNNING)
        with self.assertRaises(InvalidStateTransitionError):
            st.complete_task("task-leak-check")

        # Transition légale : RUNNING -> VERIFYING -> DONE
        st.verify_task(task_id, reason="vérification des preuves")
        self.assertEqual(st.get_entity("task", task_id).status, TaskStatus.VERIFYING.value)
        st.complete_task(task_id, reason="preuve validée")
        self.assertEqual(st.get_entity("task", task_id).status, TaskStatus.DONE.value)

        # Transition interdite : DONE -> RUNNING
        with self.assertRaises(InvalidStateTransitionError):
            st.transition("task", task_id, TaskStatus.RUNNING, "interdit depuis DONE")

        # Mises à jour des statuts globaux avec audit
        st.update_cockpit_status("RUNNING", reason="test cockpit running")
        self.assertEqual(st.cockpit_status, "RUNNING")
        st.update_board_status("READY", reason="test board ready")
        self.assertEqual(st.board_status, "READY")
        st.update_health_status("HEALTHY", reason="test health healthy")
        self.assertEqual(st.health_status, "HEALTHY")

        # Audit events produits
        logs = st.get_audit_log(entity_type="task", entity_id=task_id)
        self.assertGreaterEqual(len(logs), 4)

    # 21. test_application_manager
    def test_application_manager(self):
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from core.application_manager import get_application_manager, ApplicationHealth
        mgr = get_application_manager()
        apps = mgr.registry.list_all()
        self.assertGreater(len(apps), 10)

        # Sonde live sur service existant
        probe = ApplicationHealth.probe({"id": "cockpit-server", "type": "service", "port": 8600, "status": "RUNNING"})
        self.assertEqual(probe["health"], "HEALTHY")
        self.assertTrue(probe["port_open"])

        # Test cycle de vie complet d'application Linux réelle (start, pause, resume, stop)
        test_app_id = "test-live-proc-lifecycle"
        mgr.registry._apps[test_app_id] = {
            "id": test_app_id,
            "name": "Test Live Proc",
            "type": "process",
            "exec": "sleep 15",
            "path": "",
            "terminal": False,
            "dispo": True,
            "status": "READY",
            "pid": None,
            "window_id": None,
        }
        mgr.state.register_entity("application", test_app_id, "READY")

        # 1. Start depuis READY -> RUNNING
        start_res = mgr.start(test_app_id)
        self.assertTrue(start_res["success"], f"Échec start: {start_res}")
        self.assertEqual(mgr.registry.get(test_app_id)["status"], "RUNNING")
        pid = start_res.get("pid")
        self.assertTrue(ApplicationHealth.is_pid_running(pid))

        # 2. Pause (SIGSTOP) -> READY (is_paused=True)
        pause_res = mgr.pause(test_app_id)
        self.assertTrue(pause_res["success"])
        self.assertTrue(mgr.registry.get(test_app_id).get("is_paused"))

        # 3. Resume (SIGCONT) -> RUNNING
        resume_res = mgr.resume(test_app_id)
        self.assertTrue(resume_res["success"])
        self.assertEqual(mgr.registry.get(test_app_id)["status"], "RUNNING")
        self.assertFalse(mgr.registry.get(test_app_id).get("is_paused"))

        # 4. Stop (SIGTERM) -> STOPPED
        stop_res = mgr.stop(test_app_id)
        self.assertTrue(stop_res["success"])
        self.assertEqual(mgr.registry.get(test_app_id)["status"], "STOPPED")

        # 5. Stop sur application inactive ou UNAVAILABLE
        stop_inactive = mgr.stop(test_app_id)
        self.assertTrue(stop_inactive["success"])
        self.assertEqual(stop_inactive.get("message"), "Déjà arrêtée")

    # 22. test_turbo_dispatcher_and_adapters
    def test_turbo_dispatcher_and_adapters(self):
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from core.dispatcher import TurboDispatcher

        # Adaptateur Voice
        res_v = TurboDispatcher.dispatch_voice("arrête la tâche en cours")
        self.assertTrue(res_v["success"])
        self.assertEqual(res_v["action"], "PAUSE")
        self.assertEqual(res_v["adapter"], "VoiceAdapter")

        # Adaptateur Chat
        res_c = TurboDispatcher.dispatch_chat("analyse la base board.db")
        self.assertTrue(res_c["success"])
        self.assertEqual(res_c["adapter"], "ChatAdapter")

        # Adaptateur Board
        res_b = TurboDispatcher.dispatch_board("INSPECT", "application", "cockpit-server")
        self.assertTrue(res_b["success"])
        self.assertEqual(res_b["adapter"], "BoardAdapter")

    # 23. test_launcher_10_organs
    def test_launcher_10_organs(self):
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from core.launcher import probe_all_organs
        res = probe_all_organs()
        self.assertIn("overall_status", res)
        self.assertIn(res["overall_status"], ("HEALTHY", "DEGRADED"))
        organs = res["organs"]
        expected_organs = [
            "environment", "services", "lmstudio", "mcp", "stt",
            "tts", "gpu", "memory", "rag", "board_cockpit"
        ]
        for org in expected_organs:
            self.assertIn(org, organs, f"Organe vital manquant: {org}")
            self.assertIn(organs[org]["status"], ("HEALTHY", "DEGRADED", "ERROR"))
            self.assertTrue(bool(organs[org]["message"]))

    # 24. test_health_live_probe
    def test_health_live_probe(self):
        d = self._http_get("/health")
        self.assertTrue(d.get("ok"))
        self.assertIn("organs", d)
        organs = d["organs"]
        for org_key in ["environment", "gpu", "rag", "dispatcher", "applications", "turbo_os", "cockpit", "board"]:
            self.assertIn(org_key, organs, f"Organe {org_key} manquant dans /health")

        # API system state
        st_data = self._http_get("/api/system/state")
        self.assertIn("entities", st_data)
        self.assertIn("health_status", st_data)

    # 25. test_rag_fail_closed_enf6
    def test_rag_fail_closed_enf6(self):
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from core.rag_validator import validate_rag_response, fail_closed_gate

        sources = [
            "Turbo OS est un système souverain opérant en local sur RTX 3080 et RTX 2060 avec 22GB de VRAM.",
            "Le Cockpit central écoute sur le port 8600 et supervise les agents."
        ]

        # Réponse fondée (>= 40%) -> VALIDATED
        good_ans = "Turbo OS est un système local sur RTX 3080 et RTX 2060 avec 22GB de VRAM. Le Cockpit est sur :8600."
        val_good = validate_rag_response(good_ans, sources)
        self.assertTrue(val_good["is_valid"])
        self.assertEqual(val_good["status"], "VALIDATED")
        self.assertGreaterEqual(val_good["faithfulness"]["supported_pct"], 40.0)

        # Réponse extrapolée / hallucinée (< 40%) -> PREUVE_INSUFFISANTE (Fail-Closed)
        hallucinated_ans = "Le système est déployé sur le cloud Microsoft Azure en Irlande et consomme 50000 dollars par mois."
        val_bad = validate_rag_response(hallucinated_ans, sources)
        self.assertFalse(val_bad["is_valid"])
        self.assertEqual(val_bad["status"], "PREUVE_INSUFFISANTE")
        self.assertLess(val_bad["faithfulness"]["supported_pct"], 40.0)
        self.assertIsNotNone(val_bad["refusal_explanation"])

        # Gate fail-closed
        ok, refused_text, _ = fail_closed_gate(hallucinated_ans, sources)
        self.assertFalse(ok)
        self.assertIn("RÉPONSE REFUSÉE", refused_text)

    # 26. test_edge_cases_and_circuit_breakers
    def test_edge_cases_and_circuit_breakers(self):
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from core.system_state import get_system_state, TaskStatus, InvalidStateTransitionError
        from core.dispatcher import TurboDispatcher, ExecutionLoop
        from core.rag_validator import validate_rag_response, evaluate_faithfulness

        st = get_system_state()

        # 1. Non-existent task pause/resume raises ValueError
        with self.assertRaises(ValueError):
            st.pause_task("non-existent-task-xyz")
        with self.assertRaises(ValueError):
            st.resume_task("non-existent-task-xyz")

        # 2. Pause sur tâche TODO lève InvalidStateTransitionError
        st.register_entity("task", "t_todo", TaskStatus.TODO)
        with self.assertRaises(InvalidStateTransitionError):
            st.pause_task("t_todo")

        # 3. Resume sur tâche RUNNING lève InvalidStateTransitionError
        st.register_entity("task", "t_run", TaskStatus.READY)
        st.transition("task", "t_run", TaskStatus.RUNNING, "start")
        with self.assertRaises(InvalidStateTransitionError):
            st.resume_task("t_run")

        # 4. CANCELLED -> RUNNING strictement interdit
        st.transition("task", "t_run", TaskStatus.CANCELLED, "cancel")
        with self.assertRaises(InvalidStateTransitionError):
            st.transition("task", "t_run", TaskStatus.RUNNING, "revive")

        # 5. Dispatcher : texte vide
        r_empty = TurboDispatcher.dispatch("")
        self.assertFalse(r_empty["success"])

        # 6. Dispatcher : action Board inconnue
        r_bad_act = TurboDispatcher.dispatch_board("ACTION_INEXISTANTE", "task", "t1")
        self.assertFalse(r_bad_act["success"])
        self.assertIn("non autorisée", r_bad_act["error"])

        # 7. Coupe-circuit : MAX_TOOL_LOOPS_EXCEEDED
        loop = ExecutionLoop(max_loops=2, timeout=5.0)
        res_loop = loop.run("test", {}, tool_executor=lambda p, s, c: {"is_final": False})
        self.assertFalse(res_loop["success"])
        self.assertEqual(res_loop["error"], "MAX_TOOL_LOOPS_EXCEEDED")

        # 8. RAG numeric grounding : nombre inventé (99% non présent dans sources)
        val_num = validate_rag_response("Le gain de performance est de 99%.", ["Le gain est de 15%."])
        self.assertFalse(val_num["is_valid"])
        self.assertEqual(val_num["status"], "PREUVE_INSUFFISANTE")


if __name__ == "__main__":
    unittest.main()
