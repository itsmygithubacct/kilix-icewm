"""Provider entry-point regressions that do not require a live X display."""
import importlib.util
from importlib.machinery import SourceFileLoader
import os
from pathlib import Path
import subprocess
import tempfile
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


class TestPresentationLoop(unittest.TestCase):
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
