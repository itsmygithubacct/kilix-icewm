"""Generate IceWM's menu, toolbar, and keys from Kilix's own catalogs.

IceWM already has a menu, a taskbar, and a start button. The integration job is
therefore not to build desktop chrome -- it is to make IceWM's existing chrome
show the same things a Kilix 95 Start menu shows, from the same source of
truth, so installing something in one place cannot leave the other stale.

Everything here is pure text generation over plain dicts. It deliberately does
not import the Kilix SDK: the caller passes catalog records in, which keeps the
generator testable without a Kilix host, an X display, or a built IceWM.

IceWM menu syntax used here (see icewm(1) / menu(5) in the pinned checkout):

    prog "Label" icon program arg...      -- run a program
    menu "Label" icon {  ...  }           -- a submenu
    separator                             -- a horizontal rule

Labels are quoted and the quoting is the security-relevant part: a label is
attacker-influenced the moment a catalog record carries a name from anywhere
but us, and an unescaped quote would end the string and let the rest of the
name become IceWM command words.
"""
from __future__ import annotations

__all__ = [
    "escape_label",
    "quote_arg",
    "MenuEntry",
    "render_menu",
    "render_toolbar",
    "build_menu_model",
]

# IceWM treats a bare newline as an entry terminator, so control characters
# cannot be escaped into safety -- they have to go. They are replaced with a
# space rather than deleted: deleting them welds neighbouring words together
# ("evil\nprog" -> "evilprog"), which silently invents a token that was never
# in the source name and makes the neutralised text harder to recognise.
_STRIP = {"\n", "\r", "\x00", "\t", "\v", "\f"}


def _flatten(s: str) -> str:
    s = "".join(" " if ch in _STRIP or ord(ch) < 0x20 else ch for ch in s)
    return " ".join(s.split())


def escape_label(text: object) -> str:
    """Make ``text`` safe to place inside an IceWM double-quoted label.

    Backslash first, then the quote -- reversing that order would double-escape
    the backslashes introduced by the quote pass.
    """
    s = "" if text is None else str(text)
    s = _flatten(s)
    s = s.replace("\\", "\\\\").replace('"', '\\"')
    return s


def quote_arg(arg: object) -> str:
    """Quote one command argument for an IceWM ``prog`` line.

    IceWM splits program arguments on whitespace unless they are quoted, so any
    argument containing whitespace or a quote must come back quoted.
    """
    s = "" if arg is None else str(arg)
    s = _flatten(s)
    if s == "":
        return '""'
    if not any(c.isspace() for c in s) and '"' not in s and "\\" not in s:
        return s
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


class MenuEntry:
    """One runnable row: a label, an optional icon, and a command vector."""

    __slots__ = ("label", "command", "icon")

    def __init__(self, label: str, command, icon: str = "-"):
        if not command:
            raise ValueError("menu entry needs a command")
        self.label = label
        self.command = list(command)
        self.icon = icon or "-"

    def render(self) -> str:
        args = " ".join(quote_arg(a) for a in self.command)
        return f'prog "{escape_label(self.label)}" {quote_arg(self.icon)} {args}'

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"MenuEntry({self.label!r}, {self.command!r})"


def _section(title: str, entries, indent: str = "    ") -> list[str]:
    if not entries:
        return []
    out = [f'menu "{escape_label(title)}" folder {{']
    out.extend(indent + e.render() for e in entries)
    out.append("}")
    return out


def build_menu_model(*, catalog=(), xdg_apps=(), kilix_cmd="kilix"):
    """Turn Kilix's catalog + discovered XDG apps into ordered menu sections.

    ``catalog`` records are the pinned Kilix content entries; only the ones
    reporting themselves installed become launch rows, because an uninstalled
    row that silently does nothing is worse than an absent one. Uninstalled
    records become rows under Install instead, which is the same
    install-on-first-use behaviour the Kilix launcher offers.
    """
    games, apps, install = [], [], []
    for rec in catalog or ():
        name = rec.get("name") or rec.get("id")
        if not name:
            continue
        ident = rec.get("id") or name
        if rec.get("installed"):
            command = rec.get("command")
            if not command:
                command = (
                    [kilix_cmd, "games", "play", ident]
                    if rec.get("kind") == "game"
                    else [kilix_cmd, "app", "window", ident]
                )
            row = MenuEntry(name, command, rec.get("icon") or "-")
            (games if rec.get("kind") == "game" else apps).append(row)
        else:
            install.append(MenuEntry(f"Install {name}", [kilix_cmd, "install", ident]))

    xdg = []
    for app in xdg_apps or ():
        name = app.get("name")
        exec_cmd = app.get("exec")
        if not name or not exec_cmd:
            continue
        cmd = exec_cmd if isinstance(exec_cmd, (list, tuple)) else [exec_cmd]
        xdg.append(MenuEntry(name, list(cmd), app.get("icon") or "-"))

    for bucket in (games, apps, install, xdg):
        bucket.sort(key=lambda e: e.label.casefold())
    return {"games": games, "apps": apps, "install": install, "xdg": xdg}


def render_menu(model, *, kilix_cmd="kilix", terminal="kilix") -> str:
    """Render the full IceWM root menu."""
    lines = [
        "# Generated by kilix-icewm. Edits are overwritten on next launch.",
        "# Source of truth: the Kilix content catalog and XDG application list.",
        "",
        MenuEntry("Terminal", [terminal]).render(),
        MenuEntry(
            "Kilix Settings",
            [kilix_cmd, "--title", "Kilix Settings", kilix_cmd, "settings"],
        ).render(),
        MenuEntry(
            "Kilix Launcher",
            [kilix_cmd, "--title", "Kilix Launcher", kilix_cmd, "launcher"],
        ).render(),
        "separator",
    ]
    body = []
    body += _section("Games", model.get("games"))
    body += _section("Applications", model.get("apps"))
    body += _section("Desktop Apps", model.get("xdg"))
    body += _section("Install", model.get("install"))
    lines += body
    # Only rule off the sections that exist; with an unreadable catalog every
    # section is empty and two adjacent separators would render as a gap with
    # nothing in it.
    if body:
        lines.append("separator")
    lines.append(MenuEntry("Log Out", ["icewm-session", "--logout"]).render())
    return "\n".join(lines) + "\n"


def render_toolbar(model, *, kilix_cmd="kilix", terminal="kilix", limit=6) -> str:
    """Render the IceWM quick-launch toolbar.

    The terminal comes first and unconditionally: Kilix is the host this
    desktop runs inside, so losing a way back to a shell would strand the user
    inside a nested X server.
    """
    lines = [
        "# Generated by kilix-icewm. Edits are overwritten on next launch.",
        MenuEntry("Terminal", [terminal]).render(),
        MenuEntry(
            "Settings",
            [kilix_cmd, "--title", "Kilix Settings", kilix_cmd, "settings"],
        ).render(),
    ]
    picks = list(model.get("apps") or ()) + list(model.get("games") or ())
    for entry in picks[: max(0, int(limit))]:
        lines.append(entry.render())
    return "\n".join(lines) + "\n"
