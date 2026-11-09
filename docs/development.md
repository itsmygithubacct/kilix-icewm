# Developing Kilix IceWM

Tests, known rough edges and the repository's release position. Moved from the [README](../README.md); the text is unchanged.

## Testing

```sh
make test        # source tests; no live X desktop required
ICEWM_PARSER_SOURCE="$PWD/third_party/icewm" make test  # include native parser checks
make lint        # shellcheck, when available
```

Menu generation and configuration tests run without an X server or a running
IceWM desktop. Parser-compatibility fixtures also compile the selected IceWM
parser, so provide its pinned submodule and a C++ compiler for that coverage.

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
