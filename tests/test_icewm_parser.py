"""Optional native round trips: ICEWM_PARSER_SOURCE names an IceWM Git checkout.

Reads the provider's exact gitlink revision, independent of the source worktree
state. Compiles the upstream parser and its original helper classes, without X11
or running any menu command.
"""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from kilix_icewm.menu import quote_arg


@unittest.skipUnless(os.environ.get('ICEWM_PARSER_SOURCE'),
                     'set ICEWM_PARSER_SOURCE for pinned native parser checks')
class PinnedParserTests(unittest.TestCase):
    def test_benign_argument_vectors_round_trip(self):
        source = os.environ['ICEWM_PARSER_SOURCE']
        pin = subprocess.check_output(
            ['git', '-C', str(ROOT), 'rev-parse', 'HEAD:third_party/icewm'],
            text=True).strip()

        def upstream(path):
            return subprocess.check_output(
                ['git', '-C', source, 'show', f'{pin}:src/{path}'], text=True)

        config = upstream('yconfig.cc')
        # Preserve both complete function bodies verbatim from the pinned blob.
        parser = config[config.index('static bool isContinuedString'):
                        config.index('// FIXME: P1 - parse keys later')]
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            for header in ('ascii.h', 'argument.h'):
                (directory / header).write_text(upstream(header))
            harness = '''#include <cstring>
#include <iostream>
#include "ascii.h"
#include "argument.h"
class YConfig { public: static char* getArgument(Argument*, char*, bool); };
''' + parser + '''
int main(int argc, char** argv) {
    if (argc != 2) return 2;
    char* p = argv[1];
    while (*p) {
        while (ASCII::isSpaceOrTab(*p)) ++p;
        if (!*p) break;
        Argument result;
        char* next = YConfig::getArgument(&result, p, false);
        if (!next || next <= p) return 3;
        std::cout.write(result.cstr(), result.length());
        std::cout.put('\\0');
        p = next;
    }
}
'''
            (directory / 'parser.cc').write_text(harness)
            binary = directory / 'parser'
            subprocess.run(['c++', '-std=c++11', '-Wall', '-Wextra', '-Werror',
                            str(directory / 'parser.cc'), '-o', str(binary)], check=True)
            cases = ['', 'plain', 'annual  report.txt', ' leading ',
                     "Sam's.txt", 'folder\\file', 'trailing\\', "Sam's\\file",
                     'a"b', 'both\'"quotes\\', '\\"', "'", '"', '\\',
                     'café 日本語', 'comma,name', 'x' * 300]
            vectors = [[value] for value in cases] + [cases, ['', '', 'tail']]
            for args in vectors:
                with self.subTest(args=args):
                    command = ' '.join(quote_arg(arg) for arg in args)
                    result = subprocess.run([str(binary), command], check=True,
                                            capture_output=True)
                    self.assertEqual(result.stdout,
                                     b''.join(arg.encode() + b'\0' for arg in args))
