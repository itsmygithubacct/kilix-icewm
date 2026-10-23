"""Harmless argv/cwd checks; never execute an application or use a display."""
import os
from pathlib import Path
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from kilix_icewm import launch


class LaunchTests(unittest.TestCase):
    def test_changes_directory_before_exec_and_preserves_argv_and_display(self):
        calls = []
        with mock.patch.object(launch.os, 'chdir', side_effect=lambda p: calls.append(('cwd', p))), \
                mock.patch.object(launch.os, 'execvp', side_effect=lambda *a: calls.append(('exec', a))), \
                mock.patch.dict(os.environ, {'DISPLAY': ':isolated', 'XAUTHORITY': '/fixture/auth'}):
            self.assertEqual(launch.main(['/fixture/work dir', 'viewer', 'annual  report.txt']), 0)
            self.assertEqual(os.environ['DISPLAY'], ':isolated')
            self.assertEqual(os.environ['XAUTHORITY'], '/fixture/auth')
        self.assertEqual(calls, [('cwd', '/fixture/work dir'),
                                ('exec', ('viewer', ['viewer', 'annual  report.txt']))])

    def test_missing_directory_does_not_execute(self):
        with mock.patch.object(launch.os, 'chdir', side_effect=FileNotFoundError), \
                mock.patch.object(launch.os, 'execvp') as execute, \
                mock.patch('sys.stderr'):
            self.assertEqual(launch.main(['/missing', 'viewer']), 1)
        execute.assert_not_called()

    def test_real_process_preserves_workdir_arguments_and_display(self):
        import json
        import subprocess
        import tempfile

        with tempfile.TemporaryDirectory() as directory:
            args = ['annual  report.txt', "Sam's\\file", 'trailing\\', '']
            probe = ('import json,os,sys; '
                     'print(json.dumps([os.getcwd(),sys.argv[1:],'
                     'os.environ["DISPLAY"],os.environ["XAUTHORITY"]]))')
            result = subprocess.run(
                [sys.executable, str(Path(launch.__file__)), directory,
                 sys.executable, '-c', probe, *args],
                env=dict(os.environ, DISPLAY=':isolated', XAUTHORITY='/fixture/auth'),
                capture_output=True, text=True, check=True)
            self.assertEqual(json.loads(result.stdout),
                             [directory, args, ':isolated', '/fixture/auth'])
