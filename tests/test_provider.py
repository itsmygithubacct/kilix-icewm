"""Provider entry-point regressions that do not require a live X display."""
import importlib.util
from importlib.machinery import SourceFileLoader
import os
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
ENTRYPOINT = ROOT / "bin" / "kilix-icewm"
SPEC = importlib.util.spec_from_loader(
    "kilix_icewm_provider",
    SourceFileLoader("kilix_icewm_provider", str(ENTRYPOINT)),
)
PROVIDER = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(PROVIDER)


class TestXdgDiscovery(unittest.TestCase):
    def test_workdir_helper_runs_inside_graphical_and_terminal_entries(self):
        for terminal in (False, True):
            with self.subTest(terminal=terminal):
                sdk = SimpleNamespace(scan=lambda: [{
                    "name": "Viewer", "exec": 'viewer "annual  report.txt"',
                    "workdir": "/fixture/work dir", "terminal": terminal,
                }])
                command = PROVIDER._xdg_records(sdk, "/host/kilix")[0]["exec"]
                if terminal:
                    self.assertEqual(command[:3], ["/host/kilix", "--title", "Viewer"])
                    command = command[3:]
                self.assertEqual(command, [PROVIDER.sys.executable,
                    str(ROOT / "src/kilix_icewm/launch.py"),
                    "/fixture/work dir", "viewer", "annual  report.txt"])

    def test_sdk_scan_is_rendered_with_argv_and_terminal_presentation(self):
        sdk = SimpleNamespace(scan=mock.Mock(return_value=[
            {"name": "Native editor", "exec": 'editor --file "two words.txt"', "icon": "editor"},
            {"name": "Console", "exec": "htop --tree", "terminal": True},
        ]))
        records = PROVIDER._xdg_records(sdk, "/host/kilix")
        sdk.scan.assert_called_once_with()
        self.assertEqual(records[0]["exec"], ["editor", "--file", "two words.txt"])
        self.assertEqual(records[1]["exec"], ["/host/kilix", "--title", "Console", "htop", "--tree"])
        model = PROVIDER.build_menu_model(xdg_apps=records)
        menu = PROVIDER.render_menu(model)
        self.assertIn('menu "Desktop Apps"', menu)
        self.assertIn('editor --file "two words.txt"', menu)
        self.assertIn('/host/kilix --title Console htop --tree', menu)

    def test_unreadable_catalog_or_invalid_exec_does_not_break_menu(self):
        self.assertEqual(PROVIDER._xdg_records(SimpleNamespace(scan=mock.Mock(side_effect=OSError))), [])
        sdk = SimpleNamespace(scan=lambda: [{"name": "bad", "exec": 'unclosed "'}])
        self.assertEqual(PROVIDER._xdg_records(sdk), [])


class TestPresentationLoop(unittest.TestCase):
    def test_games_launch_inside_a_real_kilix_terminal_window(self):
        sdk = SimpleNamespace(menu_records=lambda: [{
            "id": "kilix-pong",
            "label": "Kilix Pong",
            "kind": "game",
            "icon": "pong",
            "launch_mode": "terminal",
            "capabilities": ["kitty-graphics", "kitty-keyboard"],
        }])

        records = PROVIDER._catalog_records(sdk, "/host/kilix")

        self.assertEqual(records[0]["command"], [
            "/host/kilix", "--title", "Kilix Pong",
            "/host/kilix", "games", "play", "kilix-pong",
        ])

    def test_kitty_native_apps_get_kilix_instead_of_xterm(self):
        calls = []

        def application_plan(content_id, surface, launcher):
            calls.append((content_id, surface, launcher))
            action = "run" if surface == "current" else "window"
            return SimpleNamespace(argv=(launcher, "app", action, content_id))

        sdk = SimpleNamespace(
            menu_records=lambda: [
                {
                    "id": "kilix-pdf",
                    "label": "PDF Viewer",
                    "kind": "app",
                    "icon": "pdf",
                    "launch_mode": "terminal",
                    "capabilities": ["filesystem-read", "kitty-graphics"],
                },
                {
                    "id": "kilix-calculator",
                    "label": "Calculator",
                    "kind": "app",
                    "icon": "calculator",
                    "launch_mode": "terminal",
                    "capabilities": [],
                },
            ],
            application_plan=application_plan,
        )

        records = PROVIDER._catalog_records(sdk, "/host/kilix")

        self.assertEqual(calls, [
            ("kilix-pdf", "current", "/host/kilix"),
            ("kilix-calculator", "window", "/host/kilix"),
        ])
        self.assertEqual(records[0]["command"], [
            "/host/kilix", "--title", "PDF Viewer",
            "/host/kilix", "app", "run", "kilix-pdf",
        ])
        self.assertEqual(records[1]["command"], [
            "/host/kilix", "app", "window", "kilix-calculator",
        ])

    def test_super_key_opens_the_start_menu(self):
        # Win95Keys makes a bare left Super press pop up the root menu; keeping
        # ModSuperIsCtrlAlt off stops the same key from doubling as a Ctrl+Alt
        # alias. Both are asserted as whole lines so a rename or a value change
        # in the template cannot pass unnoticed.
        for rendered in (
            PROVIDER._render_preferences(None),
            PROVIDER._render_preferences("/prefix/share/wallpaper.jpg"),
        ):
            lines = rendered.splitlines()
            self.assertIn("Win95Keys=1", lines)
            self.assertIn("ModSuperIsCtrlAlt=0", lines)

    def test_generated_config_binds_the_super_key(self):
        # The full generation path, not just the template: a provider install
        # must land the binding in the preferences file IceWM actually reads.
        with tempfile.TemporaryDirectory() as tmp:
            root = os.path.join(tmp, "icewm")
            PROVIDER.write_config(root, kilix_cmd="kilix", terminal="kilix")
            text = (Path(root) / "preferences").read_text(encoding="utf-8")
        self.assertIn("Win95Keys=1", text.splitlines())

    def test_preferences_enable_a_scaled_static_wallpaper(self):
        rendered = PROVIDER._render_preferences("/prefix/share/a wallpaper.jpg")

        self.assertIn("DesktopBackgroundCenter=0", rendered)
        self.assertIn("DesktopBackgroundScaled=1", rendered)
        self.assertIn(
            'DesktopBackgroundImage="/prefix/share/a wallpaper.jpg"',
            rendered,
        )

    def test_default_wallpaper_prefers_the_large_bundled_image(self):
        with tempfile.TemporaryDirectory() as tmp:
            large = Path(tmp) / "share/icewm/themes/NanoBlue/eos.jpg"
            fallback = Path(tmp) / "share/icewm/IceWM.jpg"
            large.parent.mkdir(parents=True)
            fallback.parent.mkdir(parents=True, exist_ok=True)
            large.write_bytes(b"large")
            fallback.write_bytes(b"fallback")

            self.assertEqual(PROVIDER._default_wallpaper(tmp), str(large))

    def test_empty_exported_prefix_uses_the_storage_prefix(self):
        with mock.patch.dict(
                os.environ, {"KILIX_ICEWM_PREFIX": ""}, clear=True):
            self.assertEqual(
                PROVIDER._icewm_prefix("/storage"),
                "/storage/prefix",
            )

    def test_explicit_prefix_is_preserved(self):
        with mock.patch.dict(
                os.environ,
                {"KILIX_ICEWM_PREFIX": "/custom/icewm"},
                clear=True):
            self.assertEqual(
                PROVIDER._icewm_prefix("/storage"),
                "/custom/icewm",
            )

    def test_delegates_to_host_runner_in_current_desktop_tab(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(
                os.environ, {"PATH": "/usr/bin", "SENTINEL": "kept"},
                clear=True), mock.patch.object(
                    PROVIDER, "_resolve_kilix_runner",
                    return_value="/host/kilix"), mock.patch.object(
                    PROVIDER.subprocess, "run",
                    return_value=subprocess.CompletedProcess([], 0)) as run:
            rc = PROVIDER._run_desktop("/prefix/bin/icewm-session", tmp)

        self.assertEqual(rc, 0)
        command = run.call_args.args[0]
        env = run.call_args.kwargs["env"]
        self.assertEqual(command, [
            "/host/kilix", "run", "--fill", "--desktop-session",
            "/prefix/bin/icewm-session",
        ])
        self.assertFalse(run.call_args.kwargs["check"])
        self.assertEqual(env["ICEWM_PRIVCFG"], tmp)
        self.assertEqual(env["XDG_CONFIG_HOME"], os.path.dirname(tmp))
        self.assertEqual(env["KILIX_RUN_AUTO_FIT"], "0")
        self.assertEqual(env["KILIX_NO_PANE"], "0")
        self.assertEqual(env["SENTINEL"], "kept")
        self.assertEqual(
            env["PATH"].split(os.pathsep),
            ["/host", "/prefix/bin", "/usr/bin"],
        )

    def test_launch_path_deduplicates_shared_executable_directory(self):
        with mock.patch.dict(os.environ, {"PATH": "/usr/bin"}, clear=True), \
                mock.patch.object(
                    PROVIDER, "_resolve_kilix_runner",
                    return_value="/prefix/bin/kilix"), mock.patch.object(
                    PROVIDER.subprocess, "run",
                    return_value=subprocess.CompletedProcess([], 0)) as run:
            rc = PROVIDER._run_desktop(
                "/prefix/bin/icewm-session", "/cfg")

        self.assertEqual(rc, 0)
        self.assertEqual(
            run.call_args.kwargs["env"]["PATH"].split(os.pathsep),
            ["/prefix/bin", "/usr/bin"],
        )

    def test_propagates_runner_exit_status(self):
        with mock.patch.object(
                PROVIDER, "_resolve_kilix_runner",
                return_value="/host/kilix"), mock.patch.object(
                    PROVIDER.subprocess, "run",
                    return_value=subprocess.CompletedProcess([], 7)):
            self.assertEqual(PROVIDER._run_desktop("/icewm", "/cfg"), 7)

    def test_reports_runner_start_failure(self):
        with mock.patch.object(
                PROVIDER, "_resolve_kilix_runner",
                return_value="/host/kilix"), mock.patch.object(
                    PROVIDER.subprocess, "run",
                    side_effect=OSError("not executable")), mock.patch(
                    "sys.stderr"):
            self.assertEqual(PROVIDER._run_desktop("/icewm", "/cfg"), 1)

    def test_missing_runner_is_actionable(self):
        with mock.patch.object(
                PROVIDER, "_resolve_kilix_runner", return_value=None), \
                mock.patch("sys.stderr"):
            self.assertEqual(PROVIDER._run_desktop("/icewm", "/cfg"), 1)

    def test_prefers_launcher_from_kilix_home(self):
        with tempfile.TemporaryDirectory() as tmp:
            runner = os.path.join(tmp, "kilix")
            Path(runner).write_text("#!/bin/sh\n", encoding="utf-8")
            os.chmod(runner, 0o755)
            with mock.patch.dict(
                    os.environ, {"KILIX_HOME": tmp, "PATH": ""}, clear=True):
                self.assertEqual(PROVIDER._resolve_kilix_runner(), runner)


if __name__ == "__main__":
    unittest.main()
