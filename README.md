# putty-osc52

**PuTTY** with patches, cross-compiled to Windows from Linux with zig.

This project can be build on Linux and Windows, and produces Putty windows executables.

## Requirements

- Linux/Windows with `uv` and `git` installed.
- Python 3.9+ (may be installed via `uv`).

## Patches

Each patch has a `.patch` file and a `.md` describing it.

### 0001: OSC 52 clipboard write

Remote programs (tmux, Vim) can write to the local clipboard via OSC 52.
Setting: Deny / Ask / Allow, default Deny. Write only, never read.

Details: [patches/0001-osc52-clipboard-write.md](patches/0001-osc52-clipboard-write.md)

## Build

`uv run` installs zig, cmake and ninja (see `pyproject.toml`) into `.venv`.

```bash
uv run build.py putty    # putty.exe only -> out/
uv run build.py dist     # all programs -> out/
uv run build.py native   # Unix build, for quick checks (Linux only)
uv run build.py resrc    # discard src/ and re-create it clean
uv run build.py clean
uv run build.py --help
```

Build trees go in `build/<platform>/`, so one checkout can be built from Linux and
Windows (e.g. a shared folder). Both would also want their own venv: set
`UV_PROJECT_ENVIRONMENT` on one of them to put it
elsewhere (e.g. off a network mount).

## How it works

- `src/` is a disposable clone of upstream, pinned by `PUTTY_REV`.
- Our changes live only in `patches/*.patch`, applied in name order.
- Editing a patch and rebuilding reverts the old patches and applies the new
  ones, so only the touched files rebuild.
- `zigtool.py` runs zig as CMake's compiler, `ar`, `ranlib` and `rc`;
  `perlshim.py` stands in for perl when the host has none. `build.py` writes
  small launchers for them into `build/<platform>/bin`.

## Changing a patch

Edit `src/`, then regenerate the patch from it:

```bash
git -C src add -A && git -C src reset -q .patched
git -C src diff --cached HEAD > patches/0001-osc52-clipboard-write.patch
```

To bump PuTTY, change `PUTTY_REV` and run `uv run build.py resrc`.
