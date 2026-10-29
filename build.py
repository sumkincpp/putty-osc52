"""Build PuTTY plus our patches. Same on Linux and Windows; stdlib only.

Run with uv, which provides the toolchain (zig, cmake, ninja): `uv run build.py putty`.
"""

import argparse
import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Callable, Iterable, Optional, Sequence, Union

StrPath = Union[str, "os.PathLike[str]"]

ROOT = Path(__file__).resolve().parent
WINDOWS = os.name == "nt"
log = logging.getLogger("build")


def rmtree(path: StrPath) -> None:
    """Remove a tree if present, including read-only files (git objects on Windows)."""

    def make_writable(func: Callable[[str], object], p: str, _exc: object) -> None:
        os.chmod(p, 0o700)
        func(p)

    if Path(path).exists():
        shutil.rmtree(path, onerror=make_writable)


def launcher_text(python: str, script: StrPath, tool: str, windows: bool) -> str:
    if windows:
        return '@"%s" "%s" %s %%*\r\n' % (python, script, tool)
    return '#!/bin/sh\nexec "%s" "%s" %s "$@"\n' % (python, script, tool)


class Builder:
    def __init__(self, build_type: str, upstream: str) -> None:
        self.build_type = build_type
        self.upstream = upstream
        self.rev = (ROOT / "PUTTY_REV").read_text().strip()
        self.src = ROOT / "src"
        self.out = ROOT / "out"
        # per host OS: a checkout shared between Linux and Windows must not share a CMake cache
        self.build_root = ROOT / "build" / sys.platform  # gitignored
        self.launchers = self.build_root / "bin"
        self.build_dir = self.build_root / "win64"
        self.native_dir = self.build_root / "native"
        # patches applied to src/ last time; lives in .git so it goes with src/
        self.applied = self.src / ".git" / "putty-applied"
        self.env = dict(
            os.environ,
            PATH=os.pathsep.join([str(self.launchers), os.environ.get("PATH", "")]),
        )

    # -- helpers -----------------------------------------------------------

    def run(self, *cmd: StrPath) -> None:
        argv = [str(c) for c in cmd]
        log.info("+ %s", " ".join(argv))
        subprocess.run(argv, env=self.env, check=True)

    def git(self, *args: StrPath) -> None:
        self.run("git", "-C", self.src, *args)

    def cmake(self, *args: StrPath) -> None:
        self.run("cmake", *args)

    @staticmethod
    def stale(path: Path, stamp: Path) -> bool:
        return not stamp.exists() or path.stat().st_mtime > stamp.stat().st_mtime

    @staticmethod
    def patches() -> list[Path]:
        return sorted((ROOT / "patches").glob("*.patch"))

    def write_launcher(self, name: str, script: str, tool: str = "") -> None:
        path = self.launchers / (name + (".cmd" if WINDOWS else ""))
        text = launcher_text(sys.executable, ROOT / script, tool, WINDOWS)
        if path.exists() and path.read_text() == text:
            return
        log.info("writing launcher %s", path)
        with open(path, "w", newline="") as f:
            f.write(text)
        path.chmod(0o755)

    def make_launchers(self) -> None:
        """Scripts CMake runs as compiler, ar, ranlib, rc (and perl, if the host has none)."""
        log.info("launchers: %s", self.launchers)
        self.launchers.mkdir(parents=True, exist_ok=True)
        for tool in ("cc", "ar", "ranlib", "rc"):
            self.write_launcher("zig-" + tool, "zigtool.py", tool)
        if shutil.which("perl") is None:
            self.write_launcher("perl", "perlshim.py")

    # -- bootstrap ---------------------------------------------------------

    def bootstrap_source(self) -> None:
        """Clone upstream at PUTTY_REV and apply patches/*.patch to src/."""
        if not (self.src / ".git").exists():
            log.info("cloning PuTTY %s into %s", self.rev, self.src)
            self.run(
                "git",
                "-c",
                "core.autocrlf=false",
                "clone",
                "-q",
                "--depth",
                "1",
                "--branch",
                self.rev,
                self.upstream,
                self.src,
            )
            self.git("config", "core.autocrlf", "false")
        stamp = self.src / ".patched"
        if not any(self.stale(p, stamp) for p in [ROOT / "PUTTY_REV"] + self.patches()):
            log.info("src/ is up to date with PUTTY_REV and patches/")
            return

        # Revert last time's patches first: only the files they touch get new
        # timestamps, so ninja does not rebuild everything. If that fails, reset.
        rev_file = self.applied / "rev"
        clean = rev_file.exists() and rev_file.read_text().strip() == self.rev
        if clean:
            for p in sorted(self.applied.glob("*.patch"), reverse=True):
                log.info("reverting %s", p.name)
                try:
                    self.git("apply", "-R", "--index", p)
                except subprocess.CalledProcessError:
                    clean = False
                    break
        if not clean:
            log.info("resetting src/ to %s", self.rev)
            self.git("checkout", "-q", "-f", self.rev)
            self.git("clean", "-fdxq")

        rmtree(self.applied)
        self.applied.mkdir(parents=True)
        for p in self.patches():
            log.info("applying %s", p.name)
            self.git("apply", "--index", p)
            shutil.copy(p, self.applied)
        rev_file.write_text(self.rev + "\n")
        stamp.touch()

    # -- targets -----------------------------------------------------------

    def bootstrap(self) -> None:
        """clone and pin src/, apply patches"""
        if not shutil.which("git"):
            sys.exit("git not found on PATH")
        self.bootstrap_source()

    def configure(self) -> None:
        self.bootstrap()
        self.make_launchers()
        log.info("configuring (%s) in %s", self.build_type, self.build_dir)
        self.cmake(
            "-S",
            self.src,
            "-B",
            self.build_dir,
            "-G",
            "Ninja",
            "-DCMAKE_BUILD_TYPE=" + self.build_type,
            "-DPUTTY_LAUNCHERS=" + self.launchers.as_posix(),
            "-DCMAKE_TOOLCHAIN_FILE=" + (ROOT / "zig-mingw.cmake").as_posix(),
        )

    def copy_to_out(self, files: Iterable[Path]) -> None:
        self.out.mkdir(exist_ok=True)
        for f in files:
            log.info("copying %s to %s", f.name, self.out)
            shutil.copy(f, self.out)

    def all(self) -> None:
        """build every program"""
        self.configure()
        log.info("building all programs")
        self.cmake("--build", self.build_dir)

    def putty(self) -> None:
        """build only putty.exe and copy it to out/"""
        self.configure()
        log.info("building putty")
        self.cmake("--build", self.build_dir, "--target", "putty")
        self.copy_to_out([self.build_dir / "putty.exe"])

    def dist(self) -> None:
        """build every program and copy the .exe files to out/"""
        self.all()
        self.copy_to_out(sorted(self.build_dir.glob("*.exe")))

    def native(self) -> None:
        """Unix build, for quick checks (Linux only)"""
        if WINDOWS:
            sys.exit("native is a Unix build; use putty or dist on Windows")
        self.bootstrap()
        self.make_launchers()
        log.info("native build in %s", self.native_dir)
        self.cmake(
            "-S",
            self.src,
            "-B",
            self.native_dir,
            "-G",
            "Ninja",
            "-DCMAKE_BUILD_TYPE=" + self.build_type,
            "-DPUTTY_GTK_VERSION=NONE",
        )
        self.cmake("--build", self.native_dir)

    def resrc(self) -> None:
        """discard src/ and re-create it clean"""
        log.info("removing %s", self.src)
        rmtree(self.src)
        self.bootstrap()

    def clean(self) -> None:
        """remove build trees and out/"""
        log.info("removing %s and %s", self.build_root, self.out)
        rmtree(self.build_root)
        rmtree(self.out)


TARGETS = ("bootstrap", "all", "putty", "dist", "native", "resrc", "clean")


def parse_args(argv: Optional[Sequence[str]]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    p.add_argument(
        "--build-type",
        default=os.environ.get("PUTTY_BUILD_TYPE", "RelWithDebInfo"),
        help="CMake build type (env PUTTY_BUILD_TYPE; default %(default)s)",
    )
    p.add_argument(
        "--upstream",
        default=os.environ.get("PUTTY_UPSTREAM", "https://git.tartarus.org/simon/putty.git"),
        help="PuTTY git URL (env PUTTY_UPSTREAM)",
    )
    sub = p.add_subparsers(dest="target", metavar="TARGET")

    for name in TARGETS:
        sub.add_parser(name, help=getattr(Builder, name).__doc__)

    args = p.parse_args(argv)
    args.target = args.target or "all"

    return args


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = parse_args(argv)
    logging.basicConfig(level=logging.INFO, stream=sys.stdout, format="%(levelname)s %(message)s")
    builder = Builder(args.build_type, args.upstream)
    try:
        log.info("target: %s", args.target)
        getattr(builder, args.target)()
        log.info("done: %s", args.target)
    except subprocess.CalledProcessError as e:
        log.error("command failed with exit code %s", e.returncode)
        sys.exit(e.returncode or 1)


if __name__ == "__main__":
    main()
