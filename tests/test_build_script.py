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

    def test_modified_source_is_refused(self):
        self.assertIn("status --porcelain", self.text)
        self.assertIn("refusing modified IceWM source", self.text)


if __name__ == "__main__":
    unittest.main()
