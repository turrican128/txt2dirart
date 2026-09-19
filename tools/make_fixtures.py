#!/usr/bin/env python3
"""Rebuild the test fixture disks in tests/fixtures/.

The fixtures are committed as binaries so that CI needs nothing but Python --
no VICE, no c1541. This script exists so they are reproducible rather than
mysterious, and so a new fixture is a one-line change instead of a hex editor
session.

    python tools/make_fixtures.py            # needs c1541 on PATH, or --c1541
    python tools/make_fixtures.py --check    # verify committed fixtures match

c1541 ships with VICE: https://vice-emu.sourceforge.io/
"""
import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures"

# name -> payload. Sizes are deliberately different so a mixed-up entry is
# obvious in a failing test (3 blocks vs 6 blocks vs 1 block).
PRGS = {
    "cracktro": bytes([0x01, 0x08]) + bytes(range(256)) * 2,
    "hrtrainer": bytes([0x01, 0x08]) + bytes(range(256)) * 5,
    "note": bytes([0x01, 0x08]) + b"HELLO" * 20,
}

DISK_NAME = "txt2dirart demo,dj"


def find_c1541(explicit=None):
    if explicit:
        return explicit
    found = shutil.which("c1541") or shutil.which("c1541.exe")
    if not found:
        sys.exit("!! c1541 not found on PATH -- pass --c1541 /path/to/c1541")
    return found


def build_three_files(c1541, dest):
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        args = [c1541, "-format", DISK_NAME, "d64", str(dest)]
        for name, payload in PRGS.items():
            p = tmp / f"{name}.prg"
            p.write_bytes(payload)
            args += ["-write", str(p), name]
        subprocess.run(args, check=True, capture_output=True)
    size = dest.stat().st_size
    if size != 174848:
        sys.exit(f"!! {dest.name}: {size} B, expected 174848")


def build_forty_track(source, dest):
    """A 40-track image: the 35-track disk plus five empty tracks of 17 sectors.

    Track 18's BAM and directory are untouched, which is exactly the point --
    the tool must accept the larger image and still only rewrite track 18.
    """
    data = bytearray(source.read_bytes())
    data += bytes(5 * 17 * 256)
    if len(data) != 196608:
        sys.exit(f"!! 40-track build came out {len(data)} B, expected 196608")
    dest.write_bytes(bytes(data))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--c1541", help="path to c1541 if it is not on PATH")
    ap.add_argument("--check", action="store_true",
                    help="rebuild into a temp dir and diff against the committed files")
    args = ap.parse_args()

    FIXTURES.mkdir(parents=True, exist_ok=True)
    out = Path(tempfile.mkdtemp()) if args.check else FIXTURES

    three = out / "three_files.d64"
    build_three_files(find_c1541(args.c1541), three)
    build_forty_track(three, out / "forty_track.d64")

    if args.check:
        bad = []
        for f in sorted(out.glob("*.d64")):
            committed = FIXTURES / f.name
            if not committed.exists():
                bad.append(f"{f.name}: not committed")
            elif committed.read_bytes() != f.read_bytes():
                bad.append(f"{f.name}: differs from committed copy")
        shutil.rmtree(out, ignore_errors=True)
        if bad:
            print("\n".join("!! " + b for b in bad))
            return 1
        print("[*] committed fixtures match a fresh build")
        return 0

    for f in sorted(FIXTURES.glob("*.d64")):
        print(f"[*] {f.name}  {f.stat().st_size} B")
    return 0


if __name__ == "__main__":
    sys.exit(main())
