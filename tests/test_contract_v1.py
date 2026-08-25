"""Shared desktop protocol-v1 surface for the independent IceWM consumer."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
ENTRY = ROOT / "bin" / "kilix-icewm"


class ContractV1Tests(unittest.TestCase):
    def run_provider(self, *arguments: str, env: dict[str, str] | None = None):
        selected = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        if env:
            selected.update(env)
        return subprocess.run(
            [sys.executable, str(ENTRY), *arguments],
            cwd=ROOT,
            env=selected,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )

    def json_endpoint(self, *arguments: str, env=None) -> dict[str, object]:
        result = self.run_provider(*arguments, env=env)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        self.assertTrue(result.stdout.endswith("\n"))
        self.assertFalse(result.stdout.endswith("\n\n"))
        return json.loads(result.stdout)

    def test_describe_is_independent_and_truthful(self):
        description = self.json_endpoint("provider", "describe", "--json")
        self.assertEqual(description["provider_id"], "kilix-icewm")
        self.assertEqual(description["display_modes"], ["x11"])
        self.assertFalse(
            description["capabilities"]["headless_screenshot"]["available"]
        )
        self.assertTrue(description["capabilities"]["reduced_motion"])

    def test_check_does_not_create_the_selected_storage(self):
        with tempfile.TemporaryDirectory() as temporary:
            storage = Path(temporary) / "must-not-exist"
            check = self.json_endpoint(
                "provider",
                "check",
                "--json",
                env={"KILIX_ICEWM_STORAGE_HOME": str(storage)},
            )
            self.assertFalse(storage.exists())
        self.assertEqual(check["provider_id"], "kilix-icewm")
        self.assertIn(check["status"], ("ready", "unavailable"))

    def test_config_reads_are_valid_and_mutations_are_gated(self):
        schema = self.json_endpoint("provider", "config", "schema", "--json")
        self.assertEqual(schema["x-kilix-provider-id"], "kilix-icewm")
        values = self.json_endpoint("provider", "config", "get", "--json")
        self.assertEqual(values["values"], {})
        for arguments in (
            ("provider", "config", "set", "theme", "NanoBlue"),
            ("provider", "migrate", "--from", "0.1.9", "--dry-run"),
            ("provider", "screenshot", "ignored.png"),
        ):
            with self.subTest(arguments=arguments):
                result = self.run_provider(*arguments)
                self.assertEqual(result.returncode, 4)
                self.assertEqual(result.stdout, "")
                self.assertIn("unavailable", result.stderr)

    def test_launch_translation_preserves_session_identity(self):
        sys.path.insert(0, str(ROOT / "src"))
        try:
            from kilix_icewm import provider_protocol

            translated = provider_protocol.dispatch(
                ["provider", "launch", "--session-id", "icewm-session-1"]
            )
            self.assertEqual(translated, [])
            self.assertEqual(
                os.environ["KILIX_DESKTOP_SESSION_ID"], "icewm-session-1"
            )
        finally:
            sys.path.remove(str(ROOT / "src"))
            for name in list(sys.modules):
                if name == "kilix_icewm" or name.startswith("kilix_icewm."):
                    sys.modules.pop(name, None)
            os.environ.pop("KILIX_DESKTOP_SESSION_ID", None)


if __name__ == "__main__":
    unittest.main()
