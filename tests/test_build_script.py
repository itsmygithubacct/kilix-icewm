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


class PartialBuildTests(unittest.TestCase):
    def test_failed_build_retry_retains_ownership_and_operator_files(self):
        import os
        import subprocess
        import tempfile
        import sys
        sys.path.insert(0, str(ROOT / 'src'))
        from kilix_icewm import install

        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            tmp = Path(tmp)
            storage = tmp / 'storage'
            build = storage / 'build'
            build.mkdir(parents=True)
            operator = build / 'operator.txt'
            operator.write_text('operator data')
            stubs = tmp / 'tools'
            stubs.mkdir()
            scripts = {
                'git': '''#!/bin/sh
case "$*" in
  *ls-tree*) echo '160000 commit pinned third_party/icewm';;
  *rev-parse*) echo pinned;;
esac
''',
                'pkg-config': '#!/bin/sh\nexit 0\n',
                'cmake': '#!/bin/sh\nmkdir -p objects\necho cache > CMakeCache.txt\n',
                'make': '''#!/bin/sh
if [ "$1" = install ]; then
  mkdir -p "$KILIX_ICEWM_STORAGE_HOME/prefix/bin"
  printf '#!/bin/sh\\nexit 0\\n' > "$KILIX_ICEWM_STORAGE_HOME/prefix/bin/icewm-session"
  chmod +x "$KILIX_ICEWM_STORAGE_HOME/prefix/bin/icewm-session"
  echo "$KILIX_ICEWM_STORAGE_HOME/prefix/bin/icewm-session" > install_manifest.txt
else
  [ -f objects/reused.o ] || echo object > objects/reused.o
  [ "$FAIL_BUILD" = 0 ] || exit 2
fi
''',
            }
            for name, contents in scripts.items():
                path = stubs / name
                path.write_text(contents)
                path.chmod(0o700)
            env = dict(os.environ, PATH=str(stubs) + os.pathsep + os.environ['PATH'],
                       KILIX_ICEWM_STORAGE_HOME=str(storage),
                       KILIX_ICEWM_PREFIX=str(storage / 'prefix'), FAIL_BUILD='1',
                       TMPDIR=str(tmp))
            first = subprocess.run(['bash', str(SCRIPT)], env=env, capture_output=True)
            self.assertNotEqual(first.returncode, 0)
            manifest = storage / 'install-manifest'
            self.assertIn('build/objects/reused.o', manifest.read_text())
            self.assertNotIn('operator.txt', manifest.read_text())
            env['FAIL_BUILD'] = '0'
            retry = subprocess.run(['bash', str(SCRIPT)], env=env, capture_output=True)
            self.assertEqual(retry.returncode, 0, retry.stderr.decode())
            self.assertIn('build/objects/reused.o', manifest.read_text())
            report = install.remove(manifest)
            self.assertTrue(report.complete)
            self.assertFalse((build / 'objects').exists())
            self.assertFalse((storage / 'prefix').exists())
            self.assertEqual(operator.read_text(), 'operator data')


if __name__ == "__main__":
    unittest.main()
