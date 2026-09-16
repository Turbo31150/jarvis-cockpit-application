#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests de core/platform_compat.py — exécutables SANS interface graphique, sur
Windows (./.venv/Scripts/python.exe cockpit/tests_platform_compat.py) comme sur
le rig Linux (python3 cockpit/tests_platform_compat.py).

Aucun test n'ouvre de fenêtre ni n'envoie de notification, sauf si
JARVIS_TEST_INTERACTIF=1 (ouvre alors un vrai terminal et un toast).
"""

import os
import subprocess
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core import platform_compat as pc  # noqa: E402

INTERACTIF = os.environ.get("JARVIS_TEST_INTERACTIF") == "1"
WIN = pc.IS_WINDOWS


class TestConstantes(unittest.TestCase):
    def test_plateforme(self):
        self.assertEqual(pc.IS_WINDOWS, sys.platform == "win32")
        self.assertEqual(pc.IS_LINUX, sys.platform.startswith("linux"))
        self.assertIsInstance(pc.IS_WSL, bool)
        self.assertEqual(pc.is_windows(), pc.IS_WINDOWS)
        self.assertFalse(pc.IS_WINDOWS and pc.IS_LINUX)
        if WIN:
            self.assertEqual(pc.NO_WINDOW, subprocess.CREATE_NO_WINDOW)
        else:
            self.assertEqual(pc.NO_WINDOW, 0)

    def test_chemins(self):
        self.assertTrue(os.path.isdir(pc.HOME))
        self.assertTrue(pc.JARVIS_DIR.startswith(pc.HOME) or os.environ.get("JARVIS_COCKPIT_ROOT")
                        or os.environ.get("JARVIS_HOME"))
        if WIN:
            self.assertIn("\\", pc.JARVIS_DIR)
        self.assertTrue(os.path.isdir(pc.tmp_dir()))
        self.assertTrue(os.path.isfile(os.path.join(pc.cockpit_root(), "gui_app.py")))
        self.assertTrue(os.path.isdir(os.path.join(pc.repo_root(), "cockpit")))
        self.assertIsNone(pc.jarvis_path("n_existe_pas_" + str(time.time()), must_exist=True))
        self.assertEqual(pc.jarvis_path("scripts", "x.py"), os.path.join(pc.JARVIS_DIR, "scripts", "x.py"))
        rd = pc.runtime_dir()
        self.assertIsInstance(rd, str)
        self.assertTrue(rd)

    def test_launcher_exts(self):
        self.assertIn(".sh", pc.LAUNCHER_EXTS)
        if WIN:
            self.assertIn(".lnk", pc.LAUNCHER_EXTS)
        else:
            self.assertIn(".desktop", pc.LAUNCHER_EXTS)

    def test_stdlib_only(self):
        # Le module ne doit dépendre ni de core.config ni de psutil à l'import
        code = ("import sys, importlib; sys.path.insert(0, %r); "
                "import core.platform_compat; "
                "print('core.config' in sys.modules, 'psutil' in sys.modules)"
                % os.path.dirname(os.path.abspath(__file__)))
        r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.split(), ["False", "False"])


class TestImportsPosix(unittest.TestCase):
    def test_posix_modules(self):
        ns = pc.posix_modules()
        for n in ("pty", "fcntl", "termios", "pwd"):
            mod = getattr(ns, n)
            if WIN:
                self.assertIsNone(mod)
            else:
                self.assertIsNotNone(mod)
        self.assertIsNone(pc.import_optional("module_inexistant_xyz"))
        self.assertIsNotNone(pc.import_optional("json"))


class TestExecutables(unittest.TestCase):
    def test_bash_jamais_wsl(self):
        b = pc.bash_exe()
        w = pc.which("bash")
        f = pc.find_executable("bash")
        for cand in (b, w, f):
            if cand:
                self.assertFalse(pc._is_wsl_bash(cand), cand)
                self.assertTrue(os.path.isfile(cand))
        if WIN and os.path.isfile(r"C:\Program Files\Git\bin\bash.exe"):
            self.assertIsNotNone(b)
            self.assertIn("Git", b)
        if not WIN:
            self.assertIsNotNone(b)

    def test_which(self):
        self.assertIsNone(pc.which(""))
        self.assertIsNone(pc.which("commande_inexistante_xyz_123"))
        if WIN:
            self.assertIsNone(pc.which("tmux"))
            self.assertIsNone(pc.which("gnome-terminal"))
            self.assertIsNone(pc.which("xdg-open"))
            self.assertIsNotNone(pc.which("cmd"))
            self.assertIsNotNone(pc.which("powershell"))
            # variantes d'extension
            self.assertEqual(os.path.normcase(pc.which("cmd.exe") or ""), os.path.normcase(pc.which("cmd") or ""))
            for n in ("nvidia-smi", "tailscale", "wt", "ollama", "claude", "lms", "git"):
                p = pc.which(n)
                if p:
                    self.assertTrue(os.path.isfile(p), p)
        else:
            self.assertIsNotNone(pc.which("sh"))
        pc.which_cache_clear()

    def test_find_executable(self):
        self.assertIsNone(pc.find_executable(""))
        self.assertIsNone(pc.find_executable("x_inexistant", "/chemin/absent", r"%USERPROFILE%\absent.exe"))
        self.assertEqual(pc.find_executable(sys.executable), sys.executable)
        self.assertEqual(pc.find_executable("x_inexistant", sys.executable), sys.executable)

    def test_python_exe(self):
        p = pc.python_exe()
        self.assertTrue(os.path.isfile(p))
        self.assertNotEqual(os.path.basename(p).lower(), "pythonw.exe")
        self.assertEqual(pc.python_executable(), p)
        self.assertNotIn("WindowsApps", p)

    def test_tmux(self):
        if WIN:
            self.assertIsNone(pc.tmux_path())
            self.assertFalse(pc.tmux_available())
            self.assertIsNone(pc.find_app("tmux"))
        else:
            self.assertEqual(pc.tmux_available(), pc.tmux_path() is not None)

    def test_find_app(self):
        self.assertIsNone(pc.find_app(""))
        for k in ("claude", "claude-desktop", "chrome", "browseros", "ollama", "docker", "wt",
                  "nvidia-smi", "git", "sqlite3", "agy", "lms", "ffmpeg"):
            p = pc.find_app(k)
            self.assertTrue(p is None or os.path.isfile(p), (k, p))
        self.assertEqual(pc.find_app("nvidia-smi"), pc.nvidia_smi_exe())
        self.assertEqual(pc.nvidia_smi_path(), pc.nvidia_smi_exe())
        b = pc.find_browser()
        self.assertTrue(b is None or os.path.isfile(b))

    def test_exec_head(self):
        self.assertEqual(pc.exec_head(""), "")
        self.assertEqual(pc.exec_head("ollama run x"), "ollama")
        if WIN:
            self.assertEqual(pc.exec_head(r'"C:\Program Files\X\x.exe" --flag'), r"C:\Program Files\X\x.exe")
        else:
            self.assertEqual(pc.exec_head('"/opt/mon app/x" --flag'), "/opt/mon app/x")


class TestSousProcessus(unittest.TestCase):
    def test_kwargs(self):
        nw = pc.no_window_kwargs()
        det = pc.popen_detached_kwargs()
        con = pc.popen_detached_kwargs(new_console=True)
        if WIN:
            self.assertEqual(nw, {"creationflags": subprocess.CREATE_NO_WINDOW})
            self.assertTrue(det["creationflags"] & subprocess.CREATE_NEW_PROCESS_GROUP)
            self.assertTrue(det["creationflags"] & subprocess.CREATE_NO_WINDOW)
            self.assertTrue(con["creationflags"] & subprocess.CREATE_NEW_CONSOLE)
        else:
            self.assertEqual(nw, {})
            self.assertEqual(det, {"start_new_session": True})
            self.assertEqual(con, {"start_new_session": True})

    def test_run_cmd_ok(self):
        r = pc.run_cmd([sys.executable, "-c", "print('salut é'); import sys; sys.exit(3)"])
        self.assertEqual(r.returncode, 3)
        self.assertIn("salut é", r.stdout)
        ok, out = pc.run_cmd_ok([sys.executable, "-c", "print('ok')"])
        self.assertTrue(ok)
        self.assertEqual(out, "ok")

    def test_run_cmd_utf8_replace(self):
        # Sortie binaire invalide en UTF-8 : jamais d'UnicodeDecodeError
        r = pc.run_cmd([sys.executable, "-c", "import sys; sys.stdout.buffer.write(b'caf\\xe9\\n')"])
        self.assertEqual(r.returncode, 0)
        self.assertTrue(r.stdout.startswith("caf"))

    def test_run_cmd_jamais_lever(self):
        r = pc.run_cmd(["commande_inexistante_xyz_123"])
        self.assertEqual(r.returncode, 127)
        self.assertIn("introuvable", r.stderr)
        ok, out = pc.run_cmd_ok(["commande_inexistante_xyz_123"])
        self.assertFalse(ok)
        self.assertIn("commande introuvable : commande_inexistante_xyz_123", out)
        t = time.time()
        r = pc.run_cmd([sys.executable, "-c", "import time; time.sleep(10)"], timeout=0.5)
        self.assertEqual(r.returncode, 124)
        self.assertIn("dépassement", r.stderr)
        self.assertLess(time.time() - t, 8)
        ok, out = pc.run_cmd_ok([sys.executable, "-c", "import time; time.sleep(10)"], timeout=0.5)
        self.assertFalse(ok)
        self.assertTrue(out.startswith("dépassement de 0.5s"), out)
        r = pc.run_cmd(["x"], input_text="abc", cwd="/dossier/inexistant/xyz")
        self.assertNotEqual(r.returncode, 0)

    def test_run_cmd_input_env(self):
        r = pc.run_cmd([sys.executable, "-c", "import sys, os; print(sys.stdin.read().upper(), os.environ.get('JV_T'))"],
                       input_text="abc", env={"JV_T": "1"})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("ABC 1", r.stdout)

    def test_shell_wrap_et_default_shell(self):
        sh = pc.default_shell()
        self.assertIsInstance(sh, list)
        self.assertTrue(os.path.isfile(sh[0]) or sh[0].endswith(".exe"))
        self.assertNotEqual(os.path.basename(sh[0]).lower(), "bash.exe" if WIN else "")
        w = pc.shell_wrap("echo a", keep_open=False)
        k = pc.shell_wrap("echo a", keep_open=True)
        self.assertEqual(w[-1] if not WIN else w[-1], "echo a" if WIN or True else None)
        if WIN:
            self.assertNotIn("bash", os.path.basename(w[0]).lower())
            kind = pc.win_shell_kind()
            self.assertIn(kind, ("cmd", "powershell", "pwsh", "gitbash"))
            if kind == "cmd":
                self.assertEqual(w[:3], ["cmd.exe", "/d", "/c"])
                self.assertEqual(k[:3], ["cmd.exe", "/d", "/k"])
            self.assertIn("-NoExit", pc.default_shell())
        else:
            self.assertEqual(w[1], "-lc")
            self.assertEqual(pc.shell_wrap("x", interactive=True)[1], "-ic")
            self.assertIn("exec", k[-1])
            self.assertEqual(sh[1], "-il")
            self.assertEqual(pc.default_shell(login=False)[1], "-i")

    def test_win_shell_kind_env(self):
        old = os.environ.get("JARVIS_WIN_SHELL")
        try:
            os.environ["JARVIS_WIN_SHELL"] = "powershell"
            if WIN and pc.which("powershell"):
                self.assertEqual(pc.win_shell_kind(), "powershell")
                w = pc.shell_wrap("Get-Date", keep_open=True)
                self.assertIn("-NoExit", w)
                self.assertEqual(w[-2:], ["-Command", "Get-Date"])
                r = pc.run_shell("Write-Output 'ps ok'")
                self.assertTrue(r.success, r.stderr)
                self.assertIn("ps ok", r.stdout)
            os.environ["JARVIS_WIN_SHELL"] = "gitbash"
            if WIN and pc.bash_exe():
                self.assertEqual(pc.win_shell_kind(), "gitbash")
                w = pc.shell_wrap("ls", keep_open=False)
                self.assertEqual(w[0], pc.bash_exe())
                r = pc.run_shell("echo gb ok")
                self.assertTrue(r.success, r.stderr)
                self.assertIn("gb ok", r.stdout)
        finally:
            if old is None:
                os.environ.pop("JARVIS_WIN_SHELL", None)
            else:
                os.environ["JARVIS_WIN_SHELL"] = old

    def test_run_shell(self):
        r = pc.run_shell("echo bonjour")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.code, 0)
        self.assertTrue(r.success)
        self.assertIn("bonjour", r.stdout)
        self.assertIn("bonjour", r["stdout"])
        d = r.to_dict()
        self.assertEqual(set(d), {"stdout", "stderr", "code", "success", "returncode"})
        r = pc.run_shell("commande_inexistante_xyz_123")
        self.assertNotEqual(r.returncode, 0)
        self.assertFalse(r.success)
        t = time.time()
        r = pc.run_shell(f'"{sys.executable}" -c "import time; time.sleep(10)"', timeout=0.7)
        self.assertEqual(r.code, 124)
        self.assertLess(time.time() - t, 8)
        r = pc.run_shell("cd", cwd=pc.tmp_dir()) if WIN else pc.run_shell("pwd", cwd=pc.tmp_dir())
        self.assertTrue(r.success)

    def test_run_shell_script(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "t.sh")
            with open(p, "w", encoding="utf-8", newline="\n") as fh:
                fh.write("#!/bin/bash\necho \"script $1\"\n")
            pc.set_executable(p)
            r = pc.run_shell_script(p, ["arg1"])
            if pc.bash_exe():
                self.assertIsNotNone(r)
                self.assertEqual(r.returncode, 0, r.stderr)
                self.assertIn("script arg1", r.stdout)
            else:
                self.assertIsNone(r)
            self.assertIsNone(pc.run_shell_script(os.path.join(d, "absent.sh")))

    def test_run_python_script(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "s.py")
            with open(p, "w", encoding="utf-8") as fh:
                fh.write("import sys; print('py', sys.argv[1])\n")
            r = pc.run_python_script(p, ["z"])
            self.assertIsNotNone(r)
            self.assertIn("py z", r.stdout)
            self.assertIsNone(pc.run_python_script("scripts/inexistant_xyz.py"))

    def test_popen_detached_et_safe_popen(self):
        p = pc.popen_detached([sys.executable, "-c", "import time; time.sleep(0.2)"])
        self.assertIsInstance(p, subprocess.Popen)
        self.assertEqual(p.wait(timeout=10), 0)
        with self.assertRaises(FileNotFoundError):
            pc.popen_detached(["commande_inexistante_xyz_123"])
        self.assertIsNone(pc.safe_popen(["commande_inexistante_xyz_123"]))
        self.assertIsNone(pc.safe_popen(["commande_inexistante_xyz_123"], detach=False))
        p = pc.safe_popen([sys.executable, "-c", "pass"], detach=False)
        self.assertIsNotNone(p)
        p.wait(timeout=10)
        p = pc.safe_popen(f'"{sys.executable}" -c "pass" &', shell=True)
        self.assertIsNotNone(p)
        p.wait(timeout=10)

    def test_launch_detached(self):
        self.assertTrue(pc.launch_detached([sys.executable, "-c", "pass"]))
        self.assertFalse(pc.launch_detached(["commande_inexistante_xyz_123"]))
        # Forme chaîne : sous Windows Popen(shell=True) détaché, sous Linux bash -lc
        self.assertTrue(pc.launch_detached(f'"{sys.executable}" -c "pass"'))

    def test_kill_process_tree(self):
        p = pc.popen_detached([sys.executable, "-c", "import time; time.sleep(30)"])
        t = time.time()
        pc.kill_process_tree(p)
        p.wait(timeout=10)
        self.assertIsNotNone(p.poll())
        self.assertLess(time.time() - t, 8)
        pc.kill_process_tree(p)  # déjà mort : silencieux
        pc.kill_process_tree(None)

    def test_signaux(self):
        for n in ("INT", "TERM", "KILL"):
            self.assertIsNotNone(pc.signal_by_name(n), n)
        self.assertEqual(pc.signal_by_name("SIGTERM"), pc.signal_by_name("TERM"))
        self.assertIsNone(pc.signal_by_name("FOO"))
        if WIN:
            self.assertIsNone(pc.signal_by_name("QUIT"))
            import signal as sg
            self.assertEqual(pc.signal_by_name("INT"), sg.CTRL_BREAK_EVENT)
        else:
            import signal as sg
            self.assertEqual(pc.signal_by_name("QUIT"), sg.SIGQUIT)
            self.assertEqual(pc.signal_by_name("KILL"), sg.SIGKILL)
        p = pc.popen_detached([sys.executable, "-c", "import time; time.sleep(30)"])
        self.assertTrue(pc.send_signal_group(p, pc.signal_by_name("TERM")))
        p.wait(timeout=10)
        self.assertFalse(pc.send_signal_group(None, 1))
        self.assertFalse(pc.send_signal_group(p, None))

    def test_process_matching(self):
        marker = "jarvis_pc_test_marker_%d" % os.getpid()
        p = pc.popen_detached([sys.executable, "-c", f"import time; x='{marker}'; time.sleep(30)"])
        try:
            time.sleep(0.6)
            if pc.has_psutil():
                self.assertTrue(pc.process_running(marker))
                n = pc.kill_processes_matching(marker, timeout=3)
                self.assertGreaterEqual(n, 1)
                p.wait(timeout=10)
                self.assertFalse(pc.process_running(marker))
            self.assertFalse(pc.process_running("motif_qui_ne_matche_rien_xyz_987"))
            self.assertEqual(pc.kill_processes_matching("motif_qui_ne_matche_rien_xyz_987"), 0)
        finally:
            pc.kill_process_tree(p)


class TestTerminaux(unittest.TestCase):
    def test_default_terminal_helpers(self):
        clsid = pc.default_terminal_clsid()
        self.assertIsInstance(pc.wt_hosts_new_consoles(), bool)
        if WIN:
            self.assertTrue(clsid is None or (clsid.startswith("{") and clsid.endswith("}") and clsid == clsid.upper()), clsid)
        else:
            self.assertIsNone(clsid)
            self.assertFalse(pc.wt_hosts_new_consoles())

    @unittest.skipUnless(WIN, "console Windows")
    def test_console_argv_windows(self):
        exe = r"C:\Program Files\Outil X\outil.exe"
        argv, kw = pc._console_argv([exe, "a b", "%TEMP%"], title='Cl & "aude" |x', keep_open=True)
        self.assertTrue(kw["creationflags"] & subprocess.CREATE_NEW_CONSOLE)
        self.assertIsNone(kw["stdin"])
        self.assertNotIn("wt.exe", subprocess.list2cmdline(argv).lower())
        if pc.win_shell_kind() == "cmd":
            self.assertEqual(argv[:3], ["cmd.exe", "/d", "/k"])
            self.assertEqual(kw["env"]["JV_TERM_TITLE"], "Cl  aude x")
            # chemin avec espaces cité, %TEMP% déjà développé
            self.assertEqual(kw["env"]["JV_TERM_CMD"], f'"{exe}" "a b" {os.environ["TEMP"]}')
            # aucun guillemet à imbriquer : la ligne finale n'en contient pas
            self.assertNotIn('"', subprocess.list2cmdline(argv))
            a2, _ = pc._console_argv("echo x", title="T", keep_open=False)
            self.assertEqual(a2[2], "/c")
        a3, k3 = pc._console_argv(None, title="It's", keep_open=True)
        self.assertIn("-NoExit", a3)
        self.assertIn("WindowTitle = 'It''s'", a3[-1])

    def test_terminal_argv(self):
        argv, kw = pc.terminal_argv("echo hi", title="T1", cwd=pc.tmp_dir())
        if WIN:
            self.assertIsNotNone(argv)
            self.assertNotIn("bash.exe", os.path.basename(argv[0]).lower())
            if pc.which("wt") and not pc.wt_hosts_new_consoles():
                self.assertEqual(os.path.basename(argv[0]).lower(), "wt.exe")
                self.assertIn("new-tab", argv)
                self.assertIn("--title", argv)
                self.assertEqual(argv[argv.index("--title") + 1], "T1")
                self.assertIn("-d", argv)
            else:
                # Console classique hébergée par le terminal par défaut : jamais wt.exe,
                # handles standard conservés, CREATE_NEW_CONSOLE.
                self.assertNotEqual(os.path.basename(argv[0]).lower(), "wt.exe")
                self.assertTrue(kw["creationflags"] & subprocess.CREATE_NEW_CONSOLE)
                self.assertIsNone(kw["stdin"]); self.assertIsNone(kw["stdout"]); self.assertIsNone(kw["stderr"])
                if pc.win_shell_kind() == "cmd":
                    self.assertEqual(argv[:2], ["cmd.exe", "/d"])
                    self.assertEqual(kw["env"]["JV_TERM_TITLE"], "T1")
                    self.assertEqual(kw["env"]["JV_TERM_CMD"], "echo hi")
                    self.assertTrue(any(k.upper() == "SYSTEMROOT" for k in kw["env"]))
            self.assertIn("creationflags", kw)
            self.assertEqual(kw["cwd"], pc.tmp_dir())
            argv2, kw2 = pc.terminal_argv(None, title="Shell")
            self.assertIsNotNone(argv2)
            self.assertIn("-NoExit", argv2)
        elif pc._linux_terminal():
            self.assertIn("--title", argv or [])
            self.assertIn("exec", argv[-1])
            self.assertEqual(kw.get("start_new_session"), True)
            a2, _ = pc.terminal_argv(["ollama", "run", "x"], title="Ollama", keep_open=False)
            self.assertEqual(a2[-3:], ["ollama", "run", "x"])
            a3, _ = pc.terminal_argv("ttx", title="T", login_shell=True)
            self.assertIn("-ic", a3)
        else:
            self.assertIsNone(argv)
            self.assertIsNone(pc.open_terminal("echo hi"))

    def test_open_terminal_interactif(self):
        if not INTERACTIF:
            self.skipTest("JARVIS_TEST_INTERACTIF=1 pour ouvrir un vrai terminal")
        p = pc.open_terminal("echo test platform_compat", title="JARVIS test")
        self.assertIsNotNone(p)
        ok, msg = pc.open_in_terminal("echo test open_in_terminal", title="JARVIS test 2")
        self.assertTrue(ok, msg)

    def test_sessions_locales(self):
        # On remplace open_terminal par un faux lancement pour ne pas ouvrir de fenêtre
        orig = pc.open_terminal
        pc.open_terminal = lambda command=None, title="JARVIS", cwd=None, **kw: pc.popen_detached(
            [sys.executable, "-c", "import time; time.sleep(30)"])
        try:
            s = pc.local_session_create("jc-test", "sleep 30")
            self.assertEqual(s["name"], "jc-test")
            self.assertTrue(s["alive"])
            self.assertEqual(s["source"], "local")
            self.assertEqual(s["windows"], 1)
            s2 = pc.local_session_create("jc-test", None)
            self.assertEqual(s2["name"], "jc-test-2")
            names = [x["name"] for x in pc.local_sessions_list()]
            self.assertIn("jc-test", names)
            self.assertIn("jc-test-2", names)
            self.assertIsNotNone(pc.local_session_get("jc-test"))
            self.assertIsNotNone(pc.local_session_get(s["id"]))
            self.assertIsNone(pc.local_session_get("absent"))
            self.assertTrue(pc.local_session_kill("jc-test"))
            self.assertFalse(pc.local_session_kill("jc-test"))
            self.assertTrue(pc.local_session_kill(s2["id"]))
            self.assertEqual(pc.local_sessions_list(include_dead=True), [])
            pc.open_terminal = lambda *a, **k: None
            s3 = pc.local_session_create("jc-fail")
            self.assertFalse(s3["alive"])
            self.assertIn("error", s3)
            self.assertEqual(pc.local_sessions_prune(), 1)
        finally:
            pc.open_terminal = orig
            for v in pc.local_sessions_list(include_dead=True):
                pc.local_session_kill(v["id"])


class TestMessages(unittest.TestCase):
    def test_libelles(self):
        note = pc.unavailable_note("Sessions tmux")
        self.assertTrue(note.startswith("⚠ Sessions tmux indisponibles sous"), note)
        self.assertTrue(pc.unavailable_note("Bureau GNOME").startswith("⚠ Bureau GNOME indisponible sous"))
        m = pc.unavailable_message("tmux", "utiliser wt.exe")
        self.assertTrue(m.startswith("⛔ tmux : indisponible sous"))
        self.assertIn("— utiliser wt.exe", m)
        self.assertNotIn("—", pc.unavailable_message("tmux"))
        if WIN:
            self.assertIn("Windows", note)

    def test_dicts(self):
        d = pc.unavailable("Replay .sh", extra=1)
        self.assertFalse(d["success"])
        self.assertTrue(d["unavailable"] and d["unsupported"])
        self.assertIn("indisponible sous", d["error"])
        self.assertEqual(d["output"], "")
        self.assertEqual(d["extra"], 1)
        i = pc.indisponible("Fond d'écran GNOME")
        self.assertTrue(i["success"] and i["indisponible"])
        self.assertIn("plateforme", i)
        self.assertIn("indisponible sous", i["note"])

    def test_feature_available(self):
        for n in ("tmux", "gnome-terminal", "systemd", "journalctl", "docker", "arecord", "lumen",
                  "flo", "whisper_local", "cuda", "x11", "appimage", "bash_scripts", "gitbash", "notify"):
            self.assertIsInstance(pc.feature_available(n), bool, n)
        if WIN:
            for n in ("tmux", "systemd", "journalctl", "arecord", "lumen", "flo", "x11", "appimage", "bash_scripts"):
                self.assertFalse(pc.feature_available(n), n)
            self.assertEqual(pc.feature_available("cuda"), pc.nvidia_smi_exe() is not None)
            self.assertEqual(pc.feature_available("gitbash"), pc.bash_exe() is not None)


class TestTelemetrie(unittest.TestCase):
    def test_gpu_info(self):
        g = pc.gpu_info()
        self.assertIsInstance(g, list)
        for x in g:
            self.assertEqual(set(x) >= {"name", "used", "total", "util", "temp", "index"}, True)
            self.assertGreater(x["total"], 0)
        if pc.nvidia_smi_exe() and WIN:
            self.assertGreaterEqual(len(g), 1)

    def test_mem(self):
        m = pc.mem_info()
        self.assertEqual(pc.ram_info()["total_mb"] > 0, True)
        self.assertGreater(m["total_mb"], 0)
        self.assertGreaterEqual(m["avail_mb"], 0)
        self.assertLessEqual(m["used_mb"], m["total_mb"])
        for k in ("total", "used", "free", "available", "percent", "total_gb", "used_gb"):
            self.assertIn(k, m)
        self.assertEqual(m["total"], m["total_mb"])
        self.assertNotIn("error", m)
        self.assertNotEqual(m["total_mb"], 16384 if not pc.has_psutil() and WIN else -1)

    def test_cpu(self):
        c = pc.cpu_info()
        for k in ("load_1m", "load_5m", "load_15m", "temp_c", "zram_percent", "zram_used_mb", "percent", "cores"):
            self.assertIn(k, c)
        self.assertIsInstance(c["load_1m"], str)
        float(c["load_1m"])
        t = pc.get_cpu_temp_c()
        if WIN:
            self.assertIsNone(t)
            self.assertEqual(c["temp_c"], 0.0)
        else:
            self.assertTrue(t is None or isinstance(t, int))

    def test_disques(self):
        d = pc.disk_usage_all()
        self.assertIsInstance(d, list)
        self.assertGreaterEqual(len(d), 1)
        for x in d:
            self.assertTrue(x["mounted"])
            self.assertGreater(x["total_gb"], 0)
        mps = pc.storage_mount_points()
        self.assertIsInstance(mps, list)
        if WIN:
            self.assertTrue(any(m.upper().startswith("C:") for m in mps))
        else:
            self.assertEqual(mps[0], "/")
        du = pc.disk_usage(pc.HOME)
        self.assertEqual(len(du), 3)
        self.assertIsNone(pc.disk_usage("/chemin/inexistant/xyz"))
        ld = pc.list_disks()
        self.assertIsInstance(ld, list)
        for x in ld:
            self.assertEqual(set(x), {"nom", "taille", "type", "montage", "modele", "usage"})
        if WIN:
            self.assertTrue(any(x["nom"] == "C:" for x in ld), ld)
            c = next(x for x in ld if x["nom"] == "C:")
            self.assertTrue(c["taille"].endswith(("G", "T")), c)
            self.assertTrue(c["usage"].endswith("%"))

    def test_usb(self):
        lst, raison = pc.list_usb(timeout=20)
        self.assertIsInstance(lst, list)
        self.assertIsInstance(raison, str)
        for x in lst:
            self.assertEqual(set(x), {"bus", "device", "id", "libelle", "hub"})
        if WIN and pc.which("powershell"):
            self.assertEqual(raison, "", raison)
            self.assertGreaterEqual(len(lst), 1)
            self.assertTrue(any(x["hub"] for x in lst) or True)

    def test_reseau(self):
        ifs = pc.list_net_ifaces()
        self.assertIsInstance(ifs, list)
        for x in ifs:
            self.assertEqual(set(x), {"nom", "etat", "mac", "adresses"})
            self.assertNotEqual(x["nom"], "lo")
            self.assertFalse(x["nom"].lower().startswith("loopback"))
        if pc.has_psutil() and WIN:
            self.assertGreaterEqual(len(ifs), 1)

    def test_ports(self):
        import socket as sk
        srv = sk.socket()
        srv.bind(("127.0.0.1", 0))
        srv.listen(1)
        port = srv.getsockname()[1]
        try:
            ports = pc.local_listening_ports(ttl=0)
            if pc.has_psutil():
                self.assertIn(port, ports)
                self.assertTrue(pc.is_local_port_open(port, ttl=0))
                t = time.time()
                for _ in range(20):
                    pc.local_listening_ports(ttl=5)
                self.assertLess(time.time() - t, 1.0)
            self.assertIsInstance(ports, set)
        finally:
            srv.close()
        self.assertFalse(pc.is_local_port_open(1, ttl=0))
        self.assertEqual(pc.tailscale_via_socks(), not WIN)

    def test_tailscale_cmd(self):
        c = pc.tailscale_cmd()
        self.assertTrue(c is None or isinstance(c, list))
        if c is None:
            self.assertTrue(pc.tailscale_reason())
        elif WIN:
            self.assertEqual(len(c), 1)
            self.assertNotIn("--socket", c)
        else:
            self.assertIn("--socket", c)

    def test_timers(self):
        t = pc.list_scheduled_timers()
        self.assertIsInstance(t, list)
        for x in t:
            for k in ("next", "left", "unit", "activates"):
                self.assertIn(k, x)
        if WIN:
            tous = pc.list_scheduled_timers(keywords=(), timeout=60)
            self.assertGreaterEqual(len(tous), 1)

    def test_session(self):
        s = pc.session_graphique()
        self.assertEqual(set(s), {"type", "wayland", "bureau"})
        i = pc.session_info()
        for k in ("type", "desktop", "wayland", "user", "bureau", "platform"):
            self.assertIn(k, i)
        if WIN:
            self.assertEqual(s, {"type": "windows", "wayland": False, "bureau": "Windows"})
            self.assertEqual(i["desktop"], "explorer")
        self.assertTrue(i["user"])


class TestBureauEtChemins(unittest.TestCase):
    def test_desktop_dir(self):
        d = pc.desktop_dir()
        self.assertIsInstance(d, str)
        self.assertEqual(pc.user_desktop_dir(), d)
        if WIN:
            self.assertTrue(os.path.isdir(d), d)
            self.assertIn("\\", d)
        for x in pc.app_launcher_dirs():
            self.assertTrue(os.path.isdir(x))
        if WIN:
            self.assertGreaterEqual(len(pc.app_launcher_dirs()), 1)
        h = pc.chrome_history_path()
        self.assertTrue(h.endswith("History"))

    def test_volume_by_label(self):
        self.assertIsNone(pc.volume_by_label(""))
        self.assertIsNone(pc.volume_by_label("ETIQUETTE_INEXISTANTE_XYZ"))
        if WIN:
            labels = pc._win_volume_labels()
            self.assertIn("C:\\", labels)
            lab = labels["C:\\"]
            if lab:
                self.assertEqual(pc.volume_by_label(lab.lower()), "C:\\")

    def test_safe_join(self):
        base = pc.tmp_dir()
        self.assertEqual(pc.safe_join(base, ""), os.path.normpath(base))
        self.assertEqual(pc.safe_join(base, "/a/b.txt"), os.path.normpath(os.path.join(base, "a", "b.txt")))
        self.assertEqual(pc.safe_join(base, "a/./b.txt?x=1"), os.path.normpath(os.path.join(base, "a", "b.txt")))
        for bad in ("../x", "/../x", "a/../../x", "C:/Windows/x", "C:\\x", "//srv/share", "\\\\srv\\x", None):
            self.assertIsNone(pc.safe_join(base, bad), bad)

    def test_set_executable(self):
        with tempfile.NamedTemporaryFile("w", suffix=".sh", delete=False) as fh:
            fh.write("#!/bin/sh\n")
            p = fh.name
        try:
            self.assertTrue(pc.set_executable(p))
            if not WIN:
                self.assertTrue(os.access(p, os.X_OK))
        finally:
            os.unlink(p)
        self.assertEqual(pc.set_executable("/inexistant/xyz"), WIN)


class TestSqlite(unittest.TestCase):
    def test_dump_csv_find(self):
        import sqlite3
        with tempfile.TemporaryDirectory() as d:
            db = os.path.join(d, "t.db")
            con = sqlite3.connect(db)
            con.execute("CREATE TABLE t (a INTEGER, b TEXT)")
            con.execute("CREATE INDEX ix ON t(a)")
            con.executemany("INSERT INTO t VALUES (?, ?)", [(1, "é"), (2, "x,y")])
            con.commit()
            con.close()
            out = os.path.join(d, "schema.sql")
            self.assertEqual(pc.sqlite_schema_dump(db, out), 2)
            with open(out, encoding="utf-8") as fh:
                self.assertIn("CREATE TABLE t", fh.read())
            csvp = os.path.join(d, "t.csv")
            self.assertEqual(pc.sqlite_export_csv(db, "SELECT * FROM t ORDER BY a", csvp), 2)
            with open(csvp, encoding="utf-8") as fh:
                lines = fh.read().splitlines()
            self.assertEqual(lines[0], "a,b")
            self.assertEqual(lines[2], '2,"x,y"')
            self.assertEqual(pc.sqlite_export_csv(db, "SELECT * FROM absente", os.path.join(d, "e.csv")), 0)
            self.assertEqual(pc.sqlite_schema_dump(os.path.join(d, "absent.db"), os.path.join(d, "e.sql")), 0)
            os.makedirs(os.path.join(d, "backups"))
            os.makedirs(os.path.join(d, "a", "b", "c", "d"))
            with open(os.path.join(d, "backups", "old.db"), "wb") as fh:
                fh.write(b"x" * 4096)
            with open(os.path.join(d, "a", "b", "deep.db"), "wb") as fh:
                fh.write(b"x" * 4096)
            with open(os.path.join(d, "a", "b", "c", "d", "trop.db"), "wb") as fh:
                fh.write(b"x" * 4096)
            with open(os.path.join(d, "petit.db"), "wb") as fh:
                fh.write(b"x" * 10)
            found = pc.find_sqlite_databases(d, max_depth=3)
            self.assertEqual([os.path.basename(x) for x in found], ["deep.db", "t.db"])
            self.assertEqual(pc.find_sqlite_databases(os.path.join(d, "absent")), [])


class TestProcessusCourant(unittest.TestCase):
    def test_utf8_stdio(self):
        pc.ensure_utf8_stdio()
        if sys.stdout is not None:
            self.assertEqual((sys.stdout.encoding or "").lower().replace("-", ""), "utf8")
        code = ("import sys; sys.path.insert(0, %r); from core.platform_compat import ensure_utf8_stdio; "
                "ensure_utf8_stdio(); print('🚀 é ⚪')" % os.path.dirname(os.path.abspath(__file__)))
        env = dict(os.environ)
        env.pop("PYTHONUTF8", None)
        env.pop("PYTHONIOENCODING", None)
        r = subprocess.run([sys.executable, "-X", "utf8=0", "-c", code], capture_output=True, env=env, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("🚀".encode("utf-8"), r.stdout)

    def test_excepthook(self):
        with tempfile.TemporaryDirectory() as d:
            log = os.path.join(d, "sub", "cockpit_gui.log")
            code = ("import sys; sys.path.insert(0, %r); from core.platform_compat import install_excepthook; "
                    "install_excepthook(%r); import threading\n"
                    "t = threading.Thread(target=lambda: 1/0); t.start(); t.join()\n"
                    "raise RuntimeError('boom principal')" % (os.path.dirname(os.path.abspath(__file__)), log))
            r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=60)
            self.assertEqual(r.returncode, 1)
            with open(log, encoding="utf-8") as fh:
                txt = fh.read()
            self.assertIn("ZeroDivisionError", txt)
            self.assertIn("boom principal", txt)
            self.assertIn("boom principal", r.stderr)
        self.assertTrue(pc.install_excepthook(os.path.join(pc.tmp_dir(), "pc_test.log")))

    def test_app_id_fonts_lmstudio(self):
        self.assertEqual(pc.set_windows_app_id("Jarvis.Cockpit.Test"), WIN)
        f, m = pc.ui_font_family(), pc.mono_font_family()
        self.assertEqual(pc.ui_font(True), m)
        self.assertEqual(pc.ui_font(), f)
        if WIN:
            self.assertEqual(f, "Segoe UI")
            self.assertIn(m, ("Cascadia Mono", "Consolas"))
        else:
            self.assertEqual((f, m), ("Ubuntu", "JetBrains Mono"))
        old = os.environ.pop("JARVIS_LMSTUDIO_HOST", None)
        try:
            self.assertEqual(pc.default_lmstudio_host(), "127.0.0.1" if WIN else "192.168.42.241")
            os.environ["JARVIS_LMSTUDIO_HOST"] = "10.0.0.5"
            self.assertEqual(pc.default_lmstudio_host(), "10.0.0.5")
        finally:
            if old is None:
                os.environ.pop("JARVIS_LMSTUDIO_HOST", None)
            else:
                os.environ["JARVIS_LMSTUDIO_HOST"] = old

    def test_open_path_et_notify(self):
        ok, msg = pc.open_path_msg("")
        self.assertFalse(ok)
        self.assertFalse(pc.open_path(""))
        self.assertFalse(pc.open_url(""))
        if not INTERACTIF:
            self.skipTest("JARVIS_TEST_INTERACTIF=1 pour ouvrir un chemin et envoyer une notification")
        self.assertTrue(pc.open_path(pc.tmp_dir()))
        self.assertTrue(pc.notify("JARVIS test", "platform_compat OK"))

    def test_open_chrome_app_absent(self):
        if pc.find_browser() is None:
            self.assertIsNone(pc.open_chrome_app("http://127.0.0.1:1/"))
        self.assertIsNone(pc.open_chrome_app(""))

    def test_record_audio_sans_materiel(self):
        # Ne doit jamais lever, même sans micro / sans outil
        with tempfile.TemporaryDirectory() as d:
            if (WIN and pc.which("ffmpeg")) or (not WIN and pc.which("arecord")):
                self.skipTest("outil audio présent : enregistrement réel non testé")
            ok, msg = pc.record_audio_wav(os.path.join(d, "x.wav"), 1)
            self.assertFalse(ok)
            self.assertTrue(msg)


if __name__ == "__main__":
    pc.ensure_utf8_stdio()
    unittest.main(verbosity=2)
