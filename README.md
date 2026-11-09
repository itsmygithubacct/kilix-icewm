# kilix-icewm

An IceWM desktop for [Kilix](https://github.com/itsmygithubacct/kilix),
selectable alongside Kilix 95, Kilix Cap, Kilix TUI and Kilix Land:

```sh
kilix icewm
```

IceWM runs on a private X display that Kilix owns, and the display is presented
into the Kilix pane. IceWM keeps its own window manager, taskbar, start menu
and workspaces; this repository supplies the Kilix integration around it.

**Status:** an optional desktop provider installed on first use by Kilix.
Kilix pins this repository (`KILIX_ICEWM_DEFAULT_REF=f6f52b04` in its
`scripts/install-kilix-icewm.sh`) and clones it to
`~/.local/gpu_terminal/sources/kilix-desktops/kilix-icewm` the first time
`kilix icewm` runs. Plebian-OS 0.2.3 (release candidate `v0.2.3-rc6`) holds the
same commit as `KILIX_ICEWM_REF` in `releases/0.2.3.env`. Kilix 95 remains the
default desktop.

IceWM itself is the upstream project [ice-wm/icewm](https://github.com/ice-wm/icewm),
licensed LGPL-2.0, pinned here as the submodule `third_party/icewm` at its
`4.1.0` tag and built unmodified.

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
| `src/kilix_icewm/provider_protocol.py` | Answers the desktop-contract `provider describe`, `check` and `config` commands without starting a display |
| `src/kilix_icewm/contract_bridge.py` | Fail-closed bridge to the staged desktop-contract command for persisted settings |
| `src/kilix_icewm/launch.py` | Runs a menu entry's argv in its declared directory, without a shell |
| `bin/kilix-icewm` | The provider entry point Kilix launches |
| `scripts/build-icewm.sh` | Fetches and builds the pinned IceWM on first use |

The private display, damage-tracked capture, RandR refit on pane resize, and
XTest injection of the kitty keyboard/mouse protocols are **not** reimplemented
here. The provider delegates its configured `icewm-session` to `kilix run`
inside the desktop tab, so those facilities come from Kilix's single app
runner implementation.

## What it does

- Starts IceWM's own session (window manager, taskbar, start menu, workspaces)
  on Kilix's private X display inside a Kilix pane.
- Generates IceWM's menu and toolbar from the Kilix content catalog and the
  installed XDG applications, so it lists what the Kilix 95 Start menu lists.
- Opens terminal-native catalog apps as `xterm` windows, Kitty-graphics apps
  and games as Kilix terminal windows, and X applications directly.
- Builds the pinned IceWM under `~/.local/gpu_terminal/kilix-icewm/prefix` on
  first use, without root, or uses a distribution IceWM.
- Rewrites its private IceWM configuration on every launch and never touches
  `~/.icewm`.
- Removes exactly what it installed, and keeps anything the user changed.

## Quick start

```sh
kilix icewm               # or: kilix desktop icewm
```

The first launch fetches and builds IceWM (CMake, pkg-config, a C++ compiler
and IceWM's development libraries are required). To use a distribution IceWM
instead:

```sh
export KILIX_ICEWM_PREFIX=/usr    # must contain bin/icewm-session
```

From a checkout, `make test` runs the source tests without an X server.

## Usage

| Command | Effect |
| --- | --- |
| `kilix icewm` | open the IceWM desktop in a Kilix page |
| `bin/kilix-icewm --check` | verify the SDK, config generation and IceWM binary without starting a display |
| `bin/kilix-icewm --print-config` | write the generated IceWM config and print its path |
| `bin/kilix-icewm --version` | print the provider version |
| `bin/kilix-icewm provider describe --json` | desktop-contract description (also `provider check --json`, `provider config ...`) |
| `make icewm` | fetch and build the pinned IceWM now |
| `make uninstall` | remove the built prefix, build tree and generated config, using the install manifests |
| `make test` / `make lint` | source tests / shellcheck |

Kilix's launcher reads `KILIX_ICEWM_DIR`, `KILIX_ICEWM_REPO`, `KILIX_ICEWM_REF`,
`KILIX_ICEWM_AUTO_INSTALL=0` and `KILIX_ICEWM_KEEP_EXISTING_CHECKOUT=1` to
change or forbid the first-use clone. In IceWM, a bare left Super press opens
the root menu and the right Super key opens the window list.

## How it works

```text
 kilix icewm
     |  Kilix clones the pinned kilix-icewm and starts bin/kilix-icewm
     v
 bin/kilix-icewm --- menu.py:    catalog + XDG apps -> IceWM menu, toolbar
     |               session.py: private ICEWM_PRIVCFG directory, supervision
     |  scripts/build-icewm.sh builds third_party/icewm once
     v
 kilix run icewm-session   (private X display, capture, input: Kilix's app runner)
     v
 Kilix pane
```

Kilix's installer verifies and advances the provider checkout to its pinned
commit; this provider then reconciles its IceWM submodule to the recorded
gitlink before building. Each launch regenerates the configuration and menus
from the catalog, then hands `icewm-session` to `kilix run`, so the display,
capture, resize and input handling are Kilix's. Details are in
[docs/installation.md](docs/installation.md) and
[docs/configuration.md](docs/configuration.md).

## Documentation

| Document | Contents |
| --- | --- |
| [docs/installation.md](docs/installation.md) | how catalog apps and games open, the lazy IceWM build, a distribution IceWM, uninstalling |
| [docs/configuration.md](docs/configuration.md) | the private regenerated configuration, Super-key preferences, menu quoting |
| [docs/development.md](docs/development.md) | tests, known rough edges and the release position |

## Related repositories

- [Kilix](https://github.com/itsmygithubacct/kilix#readme): the host, its
  `kilix icewm` verb, its app runner and the pinned installer for this
  repository.
- [ice-wm/icewm](https://github.com/ice-wm/icewm): upstream IceWM, the
  `third_party/icewm` submodule.
- [kilix-content](https://github.com/itsmygithubacct/kilix-content#readme):
  the content catalog the menus are generated from.
- [kilix-desktop-sdk](https://github.com/itsmygithubacct/kilix-desktop-sdk#readme):
  the desktop contract this provider conforms to; it records this repository
  as a separate contract consumer.
- Other Kilix desktops: [Kilix 95](https://github.com/itsmygithubacct/kilix-95#readme),
  [Kilix Cap](https://github.com/itsmygithubacct/kilix-cap#readme) and
  [Kilix Land](https://github.com/itsmygithubacct/kilix-land-desktop#readme).

## Part of Plebian-OS

kilix-icewm is one of the repositories behind
[Plebian-OS](https://github.com/itsmygithubacct/plebian-os#readme), a Debian
install whose desktop is [Kilix](https://github.com/itsmygithubacct/kilix#readme)
running the [Kilix 95](https://github.com/itsmygithubacct/kilix-95#readme)
desktop through [Pleb](https://github.com/itsmygithubacct/pleb#readme).
Kilix installs it on first use of `kilix icewm` at a pinned commit that
Plebian-OS also records. The map of every repository and how it ships is on the
[components page](https://github.com/itsmygithubacct/plebian-os/blob/main/docs/components.md).

## License

The glue in this repository is MIT; see [LICENSE](LICENSE). IceWM is
LGPL-2.0 and stays in its own submodule under its own licence.
