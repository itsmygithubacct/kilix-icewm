# Kilix IceWM installation and removal

How catalog applications appear, how IceWM is built on first use, and how the install is removed again. Moved from the [README](../README.md); the text is unchanged.

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
