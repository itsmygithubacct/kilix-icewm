"""Ownership records and the uninstall that is bounded by them.

Every case here builds a storage home by hand rather than compiling IceWM: the
manifest is the contract, and what produced the bytes it records is irrelevant
to whether removal recognises them.
"""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from kilix_icewm import install  # noqa: E402


ROOT = Path(__file__).resolve().parents[1]
ENTRYPOINT = ROOT / "bin" / "kilix-icewm"


def fake_install(storage: Path) -> Path:
    """Create the shape a real build leaves behind, and record it."""
    prefix = storage / "prefix"
    build = storage / "build"
    (prefix / "bin").mkdir(parents=True)
    (prefix / "share" / "icewm" / "themes").mkdir(parents=True)
    build.mkdir(parents=True)
    (prefix / "bin" / "icewm-session").write_text("#!/bin/sh\n", encoding="utf-8")
    (prefix / "bin" / "icewm").write_text("#!/bin/sh\n", encoding="utf-8")
    (prefix / "share" / "icewm" / "themes" / "theme").write_text("t\n", encoding="utf-8")
    (prefix / ".built-from").write_text("17907bd\n", encoding="utf-8")
    (build / "CMakeCache.txt").write_text("cache\n", encoding="utf-8")
    manifest = storage / install.INSTALL_MANIFEST
    created = sorted(install.scan_directories([prefix, build]))
    install.record_tree(manifest, [prefix, build], created)
    return manifest


class ManifestTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.storage = Path(self.tmp.name) / "kilix-icewm"
        self.storage.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def test_manifest_records_every_installed_path_relatively(self):
        manifest = fake_install(self.storage)
        text = manifest.read_text(encoding="utf-8")
        files, links, directories = install.load(manifest)

        self.assertTrue(text.startswith(install.HEADER + "\n"))
        self.assertEqual(links, [])
        self.assertEqual(
            sorted(rel for _digest, rel in files),
            [
                "build/CMakeCache.txt",
                "prefix/.built-from",
                "prefix/bin/icewm",
                "prefix/bin/icewm-session",
                "prefix/share/icewm/themes/theme",
            ],
        )
        self.assertEqual(
            sorted(directories),
            ["build", "prefix", "prefix/bin", "prefix/share",
             "prefix/share/icewm", "prefix/share/icewm/themes"],
        )
        # Relative throughout, so a manifest cannot name anything outside the
        # storage home and carries no absolute home path.
        self.assertNotIn(str(self.storage), text)

    def test_round_trip_leaves_no_orphan(self):
        manifest = fake_install(self.storage)

        report = install.remove(manifest)

        self.assertEqual(report.preserved, [])
        self.assertEqual(report.refused, [])
        self.assertEqual(report.kept, [])
        self.assertTrue(report.complete)
        self.assertEqual(len(report.removed), 5)
        self.assertEqual(len(report.pruned), 6)
        self.assertFalse(manifest.exists())
        self.assertEqual(sorted(os.listdir(self.storage)), [])

    def test_modified_file_survives_and_is_reported(self):
        manifest = fake_install(self.storage)
        edited = self.storage / "prefix" / "bin" / "icewm-session"
        edited.write_text("#!/bin/sh\necho mine\n", encoding="utf-8")

        report = install.remove(manifest)

        self.assertEqual(report.preserved, ["prefix/bin/icewm-session"])
        self.assertFalse(report.complete)
        self.assertEqual(
            edited.read_text(encoding="utf-8"), "#!/bin/sh\necho mine\n")
        # Its parents stay alive because it does, and an unfinished removal
        # keeps the manifest so the same command can finish the job later.
        self.assertIn("prefix/bin", report.kept)
        self.assertTrue(manifest.exists())
        self.assertFalse((self.storage / "prefix" / "bin" / "icewm").exists())

    def test_unowned_file_in_an_owned_directory_is_left_behind(self):
        manifest = fake_install(self.storage)
        stray = self.storage / "prefix" / "bin" / "operator-note"
        stray.write_text("keep\n", encoding="utf-8")

        report = install.remove(manifest)

        self.assertTrue(stray.is_file())
        self.assertIn("prefix/bin", report.kept)
        self.assertNotIn("prefix/bin/operator-note", report.removed)
        self.assertFalse(report.complete)

    def test_symlinked_path_component_is_refused(self):
        manifest = fake_install(self.storage)
        outside = Path(self.tmp.name) / "elsewhere"
        (outside / "themes").mkdir(parents=True)
        decoy = outside / "themes" / "theme"
        decoy.write_text("t\n", encoding="utf-8")
        share = self.storage / "prefix" / "share" / "icewm"
        for path in sorted(share.rglob("*"), reverse=True):
            if path.is_file():
                path.unlink()
            else:
                path.rmdir()
        share.rmdir()
        (self.storage / "prefix" / "share" / "icewm").symlink_to(outside)

        report = install.remove(manifest)

        # The recorded bytes are identical, so only the redirected component
        # stands between the removal and a file outside the storage home.
        self.assertEqual(decoy.read_text(encoding="utf-8"), "t\n")
        self.assertIn("prefix/share/icewm/themes/theme", report.refused)
        self.assertIn("prefix/share/icewm/themes", report.refused)
        self.assertFalse(report.complete)
        self.assertTrue(manifest.exists())
        self.assertTrue((self.storage / "prefix" / "share" / "icewm").is_symlink())

    def test_symlink_replacing_an_installed_file_is_preserved(self):
        manifest = fake_install(self.storage)
        target = Path(self.tmp.name) / "target"
        target.write_text("elsewhere\n", encoding="utf-8")
        binary = self.storage / "prefix" / "bin" / "icewm"
        binary.unlink()
        binary.symlink_to(target)

        report = install.remove(manifest)

        self.assertEqual(report.preserved, ["prefix/bin/icewm"])
        self.assertTrue(binary.is_symlink())
        self.assertEqual(target.read_text(encoding="utf-8"), "elsewhere\n")

    def test_installed_symlink_is_recorded_and_removed_by_target(self):
        (self.storage / "prefix" / "bin").mkdir(parents=True)
        (self.storage / "prefix" / "bin" / "icewm").write_text("x\n", encoding="utf-8")
        (self.storage / "prefix" / "bin" / "icewm-shell").symlink_to("icewm")
        manifest = self.storage / install.INSTALL_MANIFEST
        install.record_tree(
            manifest, [self.storage / "prefix"],
            sorted(install.scan_directories([self.storage / "prefix"])))

        _files, links, _dirs = install.load(manifest)
        self.assertEqual(links, [("icewm", "prefix/bin/icewm-shell")])

        report = install.remove(manifest)
        self.assertIn("prefix/bin/icewm-shell", report.removed)
        self.assertTrue(report.complete)

    def test_rebuild_keeps_the_directories_the_first_build_created(self):
        manifest = fake_install(self.storage)
        first = install.load(manifest)[2]

        # A second build creates none of these directories; without merging,
        # the manifest would forget it is allowed to prune them.
        (self.storage / "prefix" / "bin" / "icewm").write_text("2\n", encoding="utf-8")
        install.record_tree(
            manifest, [self.storage / "prefix", self.storage / "build"], [])

        self.assertEqual(install.load(manifest)[2], first)
        self.assertTrue(install.remove(manifest).complete)
        self.assertEqual(sorted(os.listdir(self.storage)), [])

    def test_manifest_cannot_describe_anything_outside_its_directory(self):
        manifest = self.storage / install.INSTALL_MANIFEST
        outside = Path(self.tmp.name) / "outside"
        outside.mkdir()
        (outside / "file").write_text("x\n", encoding="utf-8")

        with self.assertRaises(install.ManifestError):
            install.record_tree(manifest, [outside], [])
        with self.assertRaises(install.ManifestError):
            install.record_files(manifest, [outside / "file"])

    def test_a_manifest_naming_an_escaping_path_is_rejected(self):
        manifest = self.storage / install.INSTALL_MANIFEST
        manifest.write_text(
            install.HEADER + "\nfile\tdeadbeef\t../../.bashrc\n", encoding="utf-8")

        with self.assertRaises(install.ManifestError):
            install.remove(manifest)

    def test_a_symlinked_manifest_is_refused(self):
        real = Path(self.tmp.name) / "real-manifest"
        real.write_text(install.HEADER + "\n", encoding="utf-8")
        manifest = self.storage / install.INSTALL_MANIFEST
        manifest.symlink_to(real)

        with self.assertRaises(install.ManifestError):
            install.remove(manifest)
        self.assertTrue(real.exists())

    def test_missing_directories_answers_only_what_does_not_exist(self):
        self.assertEqual(
            install.missing_directories(self.storage / "config" / "icewm", self.storage),
            [str(self.storage / "config"), str(self.storage / "config" / "icewm")],
        )
        (self.storage / "config").mkdir()
        self.assertEqual(
            install.missing_directories(self.storage / "config" / "icewm", self.storage),
            [str(self.storage / "config" / "icewm")],
        )


class RecorderCommandTests(unittest.TestCase):
    """The two subcommands the build script drives, run the way it runs them."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.storage = Path(self.tmp.name) / "kilix-icewm"
        self.prefix = self.storage / "prefix"
        self.build = self.storage / "build"
        self.storage.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def recorder(self, *args):
        return subprocess.run(
            [sys.executable, str(ROOT / "src" / "kilix_icewm" / "install.py"), *args],
            capture_output=True, text=True, timeout=60,
        )

    def test_only_directories_the_build_created_become_prunable(self):
        # A prefix the operator made themselves, before any build ran.
        self.prefix.mkdir()
        snapshot = Path(self.tmp.name) / "snapshot"
        taken = self.recorder(
            "snapshot", "--root", str(self.prefix), "--root", str(self.build),
            "--output", str(snapshot))
        self.assertEqual(taken.returncode, 0, taken.stderr)

        (self.prefix / "bin").mkdir()
        (self.prefix / "bin" / "icewm").write_text("x\n", encoding="utf-8")
        self.build.mkdir()
        (self.build / "CMakeCache.txt").write_text("c\n", encoding="utf-8")
        manifest = self.storage / install.INSTALL_MANIFEST
        recorded = self.recorder(
            "record", "--manifest", str(manifest), "--snapshot", str(snapshot),
            "--root", str(self.prefix), "--root", str(self.build))
        self.assertEqual(recorded.returncode, 0, recorded.stderr)
        self.assertEqual(sorted(install.load(manifest)[2]),
                         ["build", "prefix/bin"])

        removed = self.recorder("remove", "--manifest", str(manifest))

        self.assertEqual(removed.returncode, 0, removed.stderr)
        self.assertFalse(self.build.exists())
        self.assertFalse((self.prefix / "bin").exists())
        # Not this install's directory, so not this install's to prune.
        self.assertTrue(self.prefix.is_dir())

    def test_removing_an_absent_manifest_is_an_error_not_a_traceback(self):
        result = self.recorder(
            "remove", "--manifest", str(self.storage / install.INSTALL_MANIFEST))

        self.assertEqual(result.returncode, 1)
        self.assertIn("no install manifest at", result.stderr)
        self.assertNotIn("Traceback", result.stderr)


class BuildScriptOwnershipTests(unittest.TestCase):
    def setUp(self):
        self.text = (ROOT / "scripts" / "build-icewm.sh").read_text(encoding="utf-8")

    def test_a_build_records_what_it_installed(self):
        self.assertIn('python3 "$RECORDER" snapshot', self.text)
        self.assertIn('python3 "$RECORDER" record --manifest "$MANIFEST"', self.text)

    def test_a_prefix_outside_the_storage_home_is_left_unclaimed(self):
        self.assertIn("records_ownership", self.text)
        self.assertIn("recording no uninstall manifest", self.text)


class UninstallVerbTests(unittest.TestCase):
    """The operator-facing command, exercised as the operator runs it."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.storage = Path(self.tmp.name) / "kilix-icewm"
        self.storage.mkdir()
        self.env = {
            "PATH": "/usr/local/bin:/usr/bin:/bin",
            "HOME": self.tmp.name,
            "KILIX_ICEWM_STORAGE_HOME": str(self.storage),
            "PYTHONDONTWRITEBYTECODE": "1",
        }

    def tearDown(self):
        self.tmp.cleanup()

    def run_uninstall(self):
        return subprocess.run(
            [sys.executable, str(ENTRYPOINT), "--uninstall"],
            env=self.env, capture_output=True, text=True, timeout=60,
        )

    def generated_config(self):
        """Write a config directory the way a launch does, manifest and all."""
        sys.path.insert(0, str(ROOT / "src"))
        from kilix_icewm.session import IceWMConfig

        manifest = self.storage / install.CONFIG_MANIFEST
        config = IceWMConfig(
            str(self.storage / "config" / "icewm"), manifest=str(manifest))
        config.write({"menu": "menu\n", "toolbar": "toolbar\n",
                      "preferences": "preferences\n"})
        return manifest

    def test_uninstall_removes_build_and_generated_config(self):
        fake_install(self.storage)
        self.generated_config()

        result = self.run_uninstall()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("removed", result.stdout)
        # The storage home itself is gone once nothing is left inside it.
        self.assertFalse(self.storage.exists())

    def test_uninstall_reports_a_user_modified_file_and_keeps_it(self):
        fake_install(self.storage)
        edited = self.storage / "prefix" / "bin" / "icewm-session"
        edited.write_text("mine\n", encoding="utf-8")

        result = self.run_uninstall()

        self.assertEqual(result.returncode, 1)
        self.assertIn("prefix/bin/icewm-session", result.stderr)
        self.assertIn("kept, not ours any more", result.stderr)
        self.assertEqual(edited.read_text(encoding="utf-8"), "mine\n")
        self.assertTrue((self.storage / install.INSTALL_MANIFEST).exists())

    def test_uninstall_refuses_a_symlinked_path_component(self):
        fake_install(self.storage)
        outside = Path(self.tmp.name) / "elsewhere"
        outside.mkdir()
        (outside / "icewm-session").write_text("#!/bin/sh\n", encoding="utf-8")
        binaries = self.storage / "prefix" / "bin"
        for path in binaries.iterdir():
            path.unlink()
        binaries.rmdir()
        binaries.symlink_to(outside)

        result = self.run_uninstall()

        self.assertEqual(result.returncode, 1)
        self.assertIn("refused, symlinked path component", result.stderr)
        self.assertIn("prefix/bin/icewm-session", result.stderr)
        self.assertTrue((outside / "icewm-session").is_file())
        self.assertTrue(binaries.is_symlink())

    def test_uninstall_without_a_manifest_says_so_and_succeeds(self):
        result = self.run_uninstall()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("nothing recorded as installed", result.stdout)

    def test_generated_config_is_recorded_where_uninstall_finds_it(self):
        manifest = self.generated_config()
        files, _links, directories = install.load(manifest)

        self.assertEqual(
            sorted(rel for _digest, rel in files),
            ["config/icewm/menu", "config/icewm/preferences",
             "config/icewm/toolbar"],
        )
        self.assertEqual(sorted(directories), ["config", "config/icewm"])

    def test_a_relaunch_keeps_the_config_directories_recorded(self):
        self.generated_config()
        manifest = self.generated_config()

        self.assertEqual(sorted(install.load(manifest)[2]),
                         ["config", "config/icewm"])
        self.assertTrue(install.remove(manifest).complete)
        self.assertFalse((self.storage / "config").exists())


if __name__ == "__main__":
    unittest.main()
