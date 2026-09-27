# kilix-icewm

An IceWM desktop for [Kilix](https://github.com/itsmygithubacct/kilix),
selectable alongside Kilix 95, Kilix Cap, Kilix TUI and Kilix Land:

```sh
kilix icewm
```

IceWM runs on a private X display that Kilix owns, and the display is presented
into the Kilix pane. IceWM keeps its own window manager, taskbar, start menu
and workspaces; this repository supplies the Kilix integration around it.

## What this repository is, and is not

It is **glue plus configuration**, not a fork of IceWM. IceWM 4.1.0 is fetched
as a submodule under `third_party/icewm`, built on request, and never modified
or vendored into this tree. That boundary is deliberate: IceWM is LGPL-2.0 and
this glue is MIT, so keeping them in separate works keeps both licences simple
to honour.

The pieces that are genuinely ours:

| File | Does |
| --- | --- |
| `src/kilix_icewm/menu.py` | Generates IceWM's `menu` and `toolbar` from the Kilix content catalog and discovered XDG applications |
| `src/kilix_icewm/session.py` | Writes IceWM a private config directory and supervises the IceWM process |
| `src/kilix_icewm/install.py` | Records what an install created, and removes exactly that |
| `bin/kilix-icewm` | The provider entry point Kilix launches |
| `scripts/build-icewm.sh` | Fetches and builds the pinned IceWM on first use |

The private display, damage-tracked capture, RandR refit on pane resize, and
XTest injection of the kitty keyboard/mouse protocols are **not** reimplemented
here. The provider delegates its configured `icewm-session` to `kilix run`
inside the desktop tab, so those facilities come from Kilix's single app
runner implementation.

## Lazily installed

Catalog applications use the host SDK's presentation plans. Terminal-native
apps such as File Manager, System Center, Settings Center, Software Center,
Voice Studio, and PDF Conversion launch through `kilix app window`, which gives
them an `xterm` PTY managed as an ordinary IceWM window; native X applications
run directly on IceWM's private display. Apps that declare Kitty graphics or
input capabilities instead open in a real Kilix terminal managed as an ordinary
IceWM window. Newly cataloged applications appear without an IceWM change.
Games use that same Kitty window and continue through `kilix games play`, so
their shared install-and-play contract receives the terminal protocols it
declares. The fixed Settings and Launcher rows use Kilix windows for the same
reason: both are interactive terminal interfaces, not background commands.

A normal clone does not fetch IceWM. The submodule is declared but left
uninitialised, so nobody pays ~57 MB and a C++ build unless they choose this
desktop. The first `kilix icewm` runs `scripts/build-icewm.sh`, which fetches
the pinned commit, builds it with CMake, and installs it under
`~/.local/gpu_terminal/kilix-icewm/prefix`. Nothing is written outside that
directory and no step needs root.

To use a distribution IceWM instead of building one:

```sh
export KILIX_ICEWM_PREFIX=/usr    # must contain bin/icewm-session
```

## Removing it again

```sh
make uninstall        # or: ./bin/kilix-icewm --uninstall
```

Every path a build creates is recorded in
`~/.local/gpu_terminal/kilix-icewm/install-manifest`, and every configuration
file a launch generates in `config-manifest` beside it. Both record digests
and paths relative to that storage home, and the uninstall removes exactly
what they list:

- a file you edited or replaced is kept, named on stderr, and the command
  exits non-zero, because the provider is then not fully removed;
- a file you added is left alone, and the directories holding it stay with it:
  only directories the install created are pruned, and only while empty;
- if any component of a recorded path has become a symlink, that path is
  refused rather than followed out of the storage home;
- an incomplete removal keeps its manifest, so resolving the difference and
  running the same command again finishes the job.

A prefix pointed outside the storage home -- a distribution IceWM, a shared
tree -- is never recorded and never removed. Neither is the source checkout
under `~/.local/gpu_terminal/sources`: the Kilix installer put it there and
owns removing it.

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

Menu labels come from catalog records, so they are escaped rather than
interpolated: a name containing a quote or a newline is neutralised instead of
being allowed to terminate its label and become IceWM command words.
`tests/test_menu.py` covers that case directly.

## Testing

```sh
make test        # 84 tests, no X display and no built IceWM required
make lint        # shellcheck, when available
```

The tests deliberately need neither an X server nor a compiled IceWM: menu
generation and config writing are pure enough to test directly, which is why
they are the parts split out into `src/`.

## Known rough edges

- **No `provider.json`.** Kilix's `check-desktop-provider.py` validates against
  Kilix 95's Python file layout (`taskbar.py`, `widgets.py`, and named markers
  inside them). Like Kilix Cap, Kilix TUI and Kilix Land, this is a native
  provider registered in the launcher rather than a manifest-validated one.

## Release position

An optional Kilix desktop provider, not a Plebian-OS release-core member. Per
`plebian-os-stack.md` the coordinated core stays `plebian-os` + `pleb` +
`kilix` + `kilix-95`; this repository takes no coordinated version or tag
obligation, and Kilix 95 remains the release default.
