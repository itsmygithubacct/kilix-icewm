"""Menu generation, with the quoting cases that decide whether a catalog name
can escape its label and become IceWM command words."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from kilix_icewm.menu import (  # noqa: E402
    MenuEntry,
    build_menu_model,
    escape_label,
    quote_arg,
    render_menu,
    render_toolbar,
)


class TestEscaping(unittest.TestCase):
    def test_plain_label_is_unchanged(self):
        self.assertEqual(escape_label("Kilix Pong"), "Kilix Pong")

    def test_quote_is_escaped_not_dropped(self):
        self.assertEqual(escape_label('A "quoted" game'), 'A \\"quoted\\" game')

    def test_backslash_escaped_before_quote(self):
        # A naive quote-then-backslash order turns \" into \\" and lets the
        # label terminate early.
        self.assertEqual(escape_label('back\\slash'), 'back\\\\slash')
        self.assertEqual(escape_label('\\"'), '\\\\\\"')

    def test_newlines_stripped_because_they_terminate_entries(self):
        self.assertEqual(escape_label("evil\nprog \"x\" - /bin/sh"),
                         'evil prog \\"x\\" - /bin/sh')
        self.assertNotIn("\n", escape_label("a\r\nb"))

    def test_none_and_nonstring(self):
        self.assertEqual(escape_label(None), "")
        self.assertEqual(escape_label(7), "7")


class TestQuoteArg(unittest.TestCase):
    def test_bare_word_not_quoted(self):
        self.assertEqual(quote_arg("chromium"), "chromium")

    def test_whitespace_forces_quoting(self):
        self.assertEqual(quote_arg("my game"), '"my game"')

    def test_empty_becomes_empty_quotes(self):
        self.assertEqual(quote_arg(""), '""')

    def test_embedded_quote_is_escaped(self):
        self.assertEqual(quote_arg('a"b'), '"a\\"b"')

    def test_argument_cannot_inject_a_second_word(self):
        rendered = MenuEntry("x", ["/bin/sh", "-c", "rm -rf /"]).render()
        self.assertIn('"rm -rf /"', rendered)


class TestModel(unittest.TestCase):
    def _catalog(self):
        return [
            {"id": "kilix-pong", "name": "Kilix Pong", "kind": "game", "installed": True},
            {"id": "bashed-earth", "name": "Bashed Earth", "kind": "game", "installed": False},
            {"id": "kilix-amp", "name": "Kilix Amp", "kind": "app", "installed": True},
            {"name": "", "installed": True},
        ]

    def test_installed_and_uninstalled_split(self):
        m = build_menu_model(catalog=self._catalog())
        self.assertEqual([e.label for e in m["games"]], ["Kilix Pong"])
        self.assertEqual([e.label for e in m["apps"]], ["Kilix Amp"])
        self.assertEqual([e.label for e in m["install"]], ["Install Bashed Earth"])

    def test_nameless_records_are_skipped(self):
        m = build_menu_model(catalog=self._catalog())
        total = sum(len(v) for v in m.values())
        self.assertEqual(total, 3)

    def test_catalog_rows_use_the_shared_game_and_application_verbs(self):
        m = build_menu_model(catalog=self._catalog())
        self.assertEqual(
            m["games"][0].command,
            ["kilix", "games", "play", "kilix-pong"],
        )
        self.assertEqual(
            m["apps"][0].command,
            ["kilix", "app", "window", "kilix-amp"],
        )
        self.assertEqual(m["install"][0].command, ["kilix", "install", "bashed-earth"])

    def test_provider_supplied_shared_plan_is_authoritative(self):
        catalog = [{
            "id": "kilix-pdf-conversion",
            "name": "PDF Conversion",
            "kind": "app",
            "icon": "doc_text",
            "installed": True,
            "command": ["/kilix", "app", "window", "kilix-pdf-conversion"],
        }]
        row = build_menu_model(catalog=catalog)["apps"][0]
        self.assertEqual(
            row.command,
            ["/kilix", "app", "window", "kilix-pdf-conversion"],
        )
        self.assertEqual(row.icon, "doc_text")

    def test_entries_sorted_case_insensitively(self):
        cat = [
            {"id": "z", "name": "zebra", "kind": "app", "installed": True},
            {"id": "a", "name": "Apple", "kind": "app", "installed": True},
        ]
        m = build_menu_model(catalog=cat)
        self.assertEqual([e.label for e in m["apps"]], ["Apple", "zebra"])

    def test_xdg_apps_accept_string_or_vector_exec(self):
        m = build_menu_model(xdg_apps=[
            {"name": "Files", "exec": "pcmanfm"},
            {"name": "Editor", "exec": ["gedit", "--new-window"]},
            {"name": "Broken"},
        ])
        self.assertEqual([e.label for e in m["xdg"]], ["Editor", "Files"])
        self.assertEqual(m["xdg"][0].command, ["gedit", "--new-window"])


class TestRender(unittest.TestCase):
    def test_menu_has_terminal_and_logout(self):
        out = render_menu(build_menu_model())
        self.assertIn('prog "Terminal"', out)
        self.assertIn('prog "Log Out"', out)

    def test_empty_sections_are_omitted_not_left_blank(self):
        out = render_menu(build_menu_model())
        self.assertNotIn('menu "Games"', out)

    def test_sections_appear_when_populated(self):
        m = build_menu_model(catalog=[
            {"id": "p", "name": "Pong", "kind": "game", "installed": True}])
        out = render_menu(m)
        self.assertIn('menu "Games" folder {', out)
        self.assertIn("}", out)

    def test_toolbar_always_offers_a_way_back_to_a_shell(self):
        out = render_toolbar(build_menu_model())
        self.assertIn('prog "Terminal"', out)

    def test_toolbar_respects_limit(self):
        cat = [{"id": f"a{i}", "name": f"App {i}", "kind": "app", "installed": True}
               for i in range(20)]
        out = render_toolbar(build_menu_model(catalog=cat), limit=3)
        self.assertEqual(out.count("prog "), 2 + 3)

    def test_hostile_catalog_name_cannot_forge_an_entry(self):
        cat = [{"id": "x", "name": 'Evil"\nprog "Pwn" - /bin/sh', "kind": "app",
                "installed": True}]
        out = render_menu(build_menu_model(catalog=cat))
        # exactly the rows we intended, plus the forged one neutralised inline
        self.assertNotIn('\nprog "Pwn"', out)
        self.assertIn('\\"', out)

    def test_output_ends_with_newline(self):
        self.assertTrue(render_menu(build_menu_model()).endswith("\n"))
        self.assertTrue(render_toolbar(build_menu_model()).endswith("\n"))


class TestSeparators(unittest.TestCase):
    def test_no_double_separator_when_catalog_is_empty(self):
        out = render_menu(build_menu_model())
        self.assertNotIn("separator\nseparator", out)

    def test_one_separator_before_logout_when_sections_exist(self):
        m = build_menu_model(catalog=[
            {"id": "p", "name": "Pong", "kind": "game", "installed": True}])
        self.assertEqual(render_menu(m).count("separator"), 2)


if __name__ == "__main__":
    unittest.main()
