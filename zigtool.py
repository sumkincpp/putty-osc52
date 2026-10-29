# Entry point for the zig tools CMake uses: cc | ar | ranlib | rc.
# Launchers made by build.py call this with the venv's python.
import os
import subprocess
import sys
from typing import Optional, Sequence


def rc_args(argv: Sequence[str]) -> list[str]:
    """windres-style args (as CMake passes them) -> zig rc args."""
    out: Optional[str] = None
    src: Optional[str] = None
    acc: list[str] = []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a in ("-o", "/fo"):
            out = argv[i + 1]
            i += 2
        elif a == "-O":
            i += 2
        elif a in ("-I", "-D"):
            acc.append("/" + a[1:] + argv[i + 1])
            i += 2
        elif a[:2] in ("-I", "-D"):
            acc.append("/" + a[1:])
            i += 1
        elif a.startswith("-"):
            i += 1
        else:
            src = a
            i += 1
    if out is None or src is None:
        sys.exit("zigtool rc: need an output file and an input file")
    return acc + ["/fo", out, src]


def main() -> None:
    tool, args = sys.argv[1], sys.argv[2:]
    if tool == "cc":
        # -UNDEBUG: zig cc defines NDEBUG when optimising; PuTTY refuses it
        target = os.environ.get("ZIG_TARGET", "x86_64-windows-gnu")
        # -mwindows: CMake's GUI-exe flag, ignored by zig cc; use an lld
        # subsystem option instead, else GUI exes get a console window
        args = [
            "-Wl,--subsystem,windows" if a == "-mwindows" else a for a in args
        ]
        args = ["-target", target, "-UNDEBUG"] + args
    elif tool == "rc":
        args = rc_args(args)
    elif tool not in ("ar", "ranlib"):
        sys.exit("zigtool: unknown tool " + tool)
    sys.exit(subprocess.call([sys.executable, "-m", "ziglang", tool] + args))


if __name__ == "__main__":
    main()
