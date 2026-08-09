"""Config-directory and process-supervision behaviour. No X display needed."""
import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from kilix_icewm.session import (  # noqa: E402
    IceWMConfig,
    IceWMProcess,
    resolve_icewm,
)


class TestConfig(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cfg = IceWMConfig(os.path.join(self.tmp.name, "icewm"))

    def tearDown(self):
        self.tmp.cleanup()

    def test_writes_known_files(self):
        self.cfg.write({"menu": "prog \"x\" - /bin/true\n", "toolbar": "\n"})
        self.assertTrue(os.path.isfile(os.path.join(self.cfg.root, "menu")))
        self.assertTrue(os.path.isfile(os.path.join(self.cfg.root, "toolbar")))

    def test_rejects_unknown_filename(self):
        # startup hooks live in this directory; an arbitrary name here would be
        # an arbitrary-file-write into a directory icewm executes from.
        with self.assertRaises(ValueError):
            self.cfg.write({"startup": "#!/bin/sh\nrm -rf /\n"})
        with self.assertRaises(ValueError):
            self.cfg.write({"../../.bashrc": "evil"})

    def test_permissions_are_private(self):
        self.cfg.write({"menu": "x\n"})
        self.assertEqual(os.stat(self.cfg.root).st_mode & 0o777, 0o700)
        self.assertEqual(
            os.stat(os.path.join(self.cfg.root, "menu")).st_mode & 0o777, 0o600)

    def test_rewrite_is_atomic_and_leaves_no_tmp(self):
        self.cfg.write({"menu": "first\n"})
        self.cfg.write({"menu": "second\n"})
        with open(os.path.join(self.cfg.root, "menu")) as fh:
            self.assertEqual(fh.read(), "second\n")
        self.assertEqual(
            [n for n in os.listdir(self.cfg.root) if n.endswith(".tmp")], [])

    def test_env_redirects_away_from_operator_dotfiles(self):
        env = self.cfg.env_for({"HOME": "/nonexistent-home"})
        self.assertEqual(env["ICEWM_PRIVCFG"], self.cfg.root)
        self.assertNotEqual(env.get("XDG_CONFIG_HOME"), "/nonexistent-home/.config")


class TestResolve(unittest.TestCase):
    def test_prefers_our_prefix_over_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            bindir = os.path.join(tmp, "bin")
            os.makedirs(bindir)
            fake = os.path.join(bindir, "icewm-session")
            with open(fake, "w") as fh:
                fh.write("#!/bin/sh\n")
            os.chmod(fake, 0o755)
            session, _wm = resolve_icewm(prefix=tmp, env={})
            self.assertEqual(session, fake)

    def test_missing_returns_none_rather_than_raising(self):
        with tempfile.TemporaryDirectory() as tmp:
            session, wm = resolve_icewm(prefix=tmp, env={"PATH": tmp})
            self.assertIsNone(session)
            self.assertIsNone(wm)


class TestProcess(unittest.TestCase):
    def test_requires_a_binary(self):
        with self.assertRaises(ValueError):
            IceWMProcess("", ":99")

    def test_stop_is_safe_before_start(self):
        IceWMProcess("/bin/true", ":99").stop()   # must not raise

    def test_stop_terminates_a_running_process(self):
        p = IceWMProcess("/bin/sh", ":99")
        p.proc = subprocess.Popen(
            ["/bin/sh", "-c", "sleep 60"], stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
            start_new_session=True)
        p.stop(timeout=3.0)
        self.assertIsNotNone(p.poll())

    def test_failure_text_reports_stderr(self):
        p = IceWMProcess("/bin/sh", ":99")
        p.proc = subprocess.Popen(
            ["/bin/sh", "-c", "echo 'cannot open display' >&2; exit 1"],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE, start_new_session=True)
        p.proc.wait(timeout=5)
        self.assertIn("cannot open display", p.failure_text())

    def test_display_and_xauthority_reach_the_child_env(self):
        p = IceWMProcess("/bin/true", ":42", env={}, xauthority="/tmp/xa")
        self.assertEqual(p.env["DISPLAY"], ":42")
        self.assertEqual(p.env["XAUTHORITY"], "/tmp/xa")


if __name__ == "__main__":
    unittest.main()
