import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "build-icewm.sh"


class BuildScriptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = SCRIPT.read_text(encoding="utf-8")

    def test_initialized_source_is_reconciled_to_the_gitlink(self):
        self.assertIn('[ "$have" != "$want" ]', self.text)
        self.assertIn(
            "submodule update --init --recursive --checkout --", self.text
        )

    def test_selected_source_must_match_the_gitlink(self):
        self.assertIn("does not match pinned commit", self.text)

    def test_submodule_progress_does_not_pollute_the_commit_stamp(self):
        self.assertRegex(
            self.text,
            r'"\$SUBMODULE_PATH"\s+>&2\s+\\\s*\n\s*\|\| die',
        )

    def test_modified_source_is_refused(self):
        self.assertIn("status --porcelain", self.text)
        self.assertIn("refusing modified IceWM source", self.text)

    def test_preflight_covers_required_icewm_development_modules(self):
        for module in (
            "xrender",
            "xcomposite",
            "xcursor",
            "xdamage",
            "xfixes",
            "imlib2",
        ):
            with self.subTest(module=module):
                self.assertIn(module, self.text)
        self.assertIn("libimlib2-dev", self.text)

    def test_stale_cmake_cache_error_prints_the_recovery_commands(self):
        self.assertIn("CMAKE_HOME_DIRECTORY:INTERNAL=", self.text)
        self.assertIn("stale CMake build cache", self.text)
        self.assertIn("Clear the generated build directory and retry", self.text)
        self.assertIn("rm -rf -- $escaped_build_dir", self.text)
        self.assertIn("kilix icewm", self.text)


if __name__ == "__main__":
    unittest.main()
