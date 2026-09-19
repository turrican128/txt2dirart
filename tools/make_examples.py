#!/usr/bin/env python3
"""Build examples.d64 -- the demo disk that ships alongside the release.

The point of this disk is that you do not have to install anything to see
what the tool does: attach it, LIST it, and the directory itself is the
demonstration. LOAD"DEMO",8 and RUN proves the files still work.

    python tools/make_examples.py                 # stamp the committed base
    python tools/make_examples.py --rebuild-base  # re-master it (needs c1541)

Two stages, deliberately split:

  1. MASTER  format a disk and write the BASIC demos onto it. Needs c1541,
             so the result is committed as tools/examples-base.d64 and only
             rebuilt when the demo programs change.
  2. STAMP   put the art on it. Pure Python, no dependencies.

Splitting them is what lets CI verify the shipped examples.d64 is current
without installing an emulator: it re-runs stage 2 and diffs. A committed
binary that nothing checks drifts out of date silently.

Output: examples.d64 in the repo root.
"""
import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import txt2dirart  # noqa: E402

DISK_NAME = "txt2dirart 1.0,dj"

BASIC_LINES = [
    (10, '?"{}TXT2DIRART 1.0"'),
    (20, '?"DIR ART FROM A TEXT FILE"'),
    (30, '?"BY DR.J/DELYSID"'),
    (40, '?""'),
    (50, '?"THE LISTING YOU JUST SAW"'),
    (60, '?"IS WHAT THIS TOOL MAKES."'),
]

README_LINES = [
    (10, '?"TXT2DIRART"'),
    (20, '?"GITHUB.COM/TURRICAN128"'),
    (30, '?"/TXT2DIRART"'),
]

# The handful of BASIC tokens this demo needs. '?' is the standard
# abbreviation for PRINT and tokenises to the same $99.
TOKENS = {"?": 0x99}


def tokenize_line(number, text):
    """Tokenise one BASIC line body (without the link bytes)."""
    out = bytearray()
    out += number.to_bytes(2, "little")
    in_quotes = False
    i = 0
    while i < len(text):
        ch = text[i]
        if ch == '"':
            in_quotes = not in_quotes
            out.append(ord('"'))
            i += 1
            continue
        if not in_quotes and ch in TOKENS:
            out.append(TOKENS[ch])
            i += 1
            continue
        if in_quotes and ch == "{" and text[i:i + 2] == "{}":
            out.append(0x93)                 # clear screen
            i += 2
            continue
        out.append(ord(ch.upper()))
        i += 1
    out.append(0x00)
    return bytes(out)


def build_basic(lines, load_addr=0x0801):
    """Assemble tokenised lines into a runnable .prg."""
    bodies = [tokenize_line(n, t) for n, t in lines]
    # Link pointers are absolute addresses, so they can only be filled in
    # once every line's length is known.
    addr = load_addr
    offsets = []
    for body in bodies:
        offsets.append(addr)
        addr += 2 + len(body)
    end = addr

    prg = bytearray(load_addr.to_bytes(2, "little"))
    for i, body in enumerate(bodies):
        # The LAST line links to the $0000 terminator that follows it, not to
        # zero. A last link of zero makes BASIC stop *before* that line, and
        # the line silently never runs.
        nxt = offsets[i + 1] if i + 1 < len(offsets) else end
        prg += nxt.to_bytes(2, "little")
        prg += body
    prg += (0).to_bytes(2, "little")
    return bytes(prg)


def find_c1541(explicit=None):
    found = explicit or shutil.which("c1541") or shutil.which("c1541.exe")
    if not found:
        sys.exit("!! c1541 not found on PATH -- pass --c1541 /path/to/c1541")
    return found


BASE = ROOT / "tools" / "examples-base.d64"
ART = ROOT / "tools" / "examples-disk-art.txt"


def rebuild_base(c1541, dest):
    """Stage 1: master a fresh disk with the BASIC demos on it."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        demo = tmp / "demo.prg"
        demo.write_bytes(build_basic(BASIC_LINES))
        readme = tmp / "readme.prg"
        readme.write_bytes(build_basic(README_LINES))

        subprocess.run(
            [c1541, "-format", DISK_NAME, "d64", str(dest),
             "-write", str(demo), "demo",
             "-write", str(readme), "readme"],
            check=True, capture_output=True)
    print(f"[*] mastered {dest.name}  {dest.stat().st_size} B")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rebuild-base", action="store_true",
                    help="re-master the base disk with c1541 (only needed when "
                         "the demo programs change)")
    ap.add_argument("--c1541", help="path to c1541 if it is not on PATH")
    ap.add_argument("-o", "--out", default=str(ROOT / "examples.d64"))
    args = ap.parse_args()

    if args.rebuild_base:
        rebuild_base(find_c1541(args.c1541), BASE)

    if not BASE.exists():
        sys.exit(f"!! {BASE} is missing -- run with --rebuild-base (needs c1541)")

    out = Path(args.out)
    stamped, _ = txt2dirart.stamp(
        BASE.read_bytes(), txt2dirart.art_from_text(ART), log=lambda *a, **k: None)
    out.write_bytes(stamped)

    print(f"[*] {out}  {out.stat().st_size} B")
    print()
    txt2dirart.print_listing(stamped, txt2dirart.read_chain(bytearray(stamped))[1])
    return 0


if __name__ == "__main__":
    sys.exit(main())
