#!/usr/bin/env python3
"""Drive VICE to photograph examples.d64 on a real C64, for docs/ and CSDb.

This is the one check nothing else can do. `--dry-run` and c1541 both show
you *bytes*; only a C64 shows you the glyphs those bytes turn into. A \\xNN
taken from the wrong chart looks perfectly correct everywhere except here.

    python tools/capture_screens.py                 # needs x64sc on PATH
    python tools/capture_screens.py --x64sc PATH

Two captures:
    docs/listing-on-a-c64.png   LOAD"$",8 + LIST -- the art as the drive lists it
    docs/demo-running.png       LOAD"DEMO",8 + RUN -- proof the files still load

Notes for anyone changing this:

  * -keybuf wants LOWERCASE ascii. Uppercase goes in as PETSCII $C1-$DA,
    which are graphics characters in the boot charset, and you get a
    screenful of garbage that looks like a disk problem.
  * The line terminator must be \\n. A \\r is typed but never submits.
  * -limitcycles ends the run; VICE exits non-zero when it does, which is
    expected and not a failure.
"""
import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DISK = ROOT / "examples.d64"
DOCS = ROOT / "docs"

PAL_CYCLES_PER_SEC = 985_248

SHOTS = [
    ("listing-on-a-c64.png", 'load"$",8\nlist\n', 40),
    ("demo-running.png", 'load"demo",8\nrun\n', 40),
]


def find_x64sc(explicit=None):
    found = explicit or shutil.which("x64sc") or shutil.which("x64sc.exe")
    if not found:
        sys.exit("!! x64sc not found on PATH -- pass --x64sc /path/to/x64sc")
    return found


def capture(x64sc, disk, keys, seconds, dest):
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        dest.unlink()
    subprocess.run(
        [x64sc, "-default", "-8", str(disk),
         "-keybuf", keys,
         "-limitcycles", str(seconds * PAL_CYCLES_PER_SEC),
         "-exitscreenshot", str(dest)],
        capture_output=True)                  # exits non-zero on -limitcycles
    if not dest.exists() or dest.stat().st_size == 0:
        sys.exit(f"!! no screenshot written to {dest}")
    print(f"[*] {dest.relative_to(ROOT)}  {dest.stat().st_size} B")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--x64sc")
    ap.add_argument("--disk", default=str(DISK))
    args = ap.parse_args()

    disk = Path(args.disk)
    if not disk.exists():
        sys.exit(f"!! {disk} is missing -- run tools/make_examples.py first")

    x64sc = find_x64sc(args.x64sc)
    for name, keys, seconds in SHOTS:
        capture(x64sc, disk, keys, seconds, DOCS / name)

    print("\n[*] Look at both. The listing must match the art you wrote, and")
    print("    the demo must print every one of its lines.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
