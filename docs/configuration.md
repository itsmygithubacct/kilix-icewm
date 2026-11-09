# Kilix IceWM configuration

Where the generated IceWM configuration lives and why it is rewritten on every launch. Moved from the [README](../README.md); the text is unchanged.

## Configuration is private and regenerated

IceWM is pointed at `~/.local/gpu_terminal/kilix-icewm/config/icewm` through
`ICEWM_PRIVCFG`, written `0700` with `0600` files, and rewritten on every
launch. It never reads or writes the operator's `~/.icewm`, and a crashed
session cannot leave half-written configuration behind.

Only the four generated filenames are writable through that path. The
directory is one IceWM executes startup hooks from, so accepting an arbitrary
filename there would be an arbitrary-file-write into an executable location.

The generated preferences make the Windows/Super key the start button:
`Win95Keys=1` opens IceWM's root menu on a bare left Super press (the right
one opens the window list), and `ModSuperIsCtrlAlt=0` keeps Super a dedicated
key instead of an alias for Ctrl+Alt combinations.

Menu generation follows the selected IceWM parser's actual quoting rules.
Unsupported command, icon, working-directory or catalog rows are skipped
individually with diagnostics; fixed desktop actions remain available.
`tests/test_menu.py` covers this boundary, including selected-parser fixtures.
