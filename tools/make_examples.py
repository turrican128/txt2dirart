#!/usr/bin/env python3
"""Build examples.d64 -- the demo disk that ships alongside the release.

The point of this disk is that you do not have to install anything to see
what the tool does: attach it, LIST it, and the directory itself is the
demonstration. LOAD"DEMO",8 and RUN proves the files still work.

    python tools/make_examples.py                 # needs c1541 on PATH
    python tools/make_examples.py --c1541 PATH

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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--c1541")
    ap.add_argument("-o", "--out", default=str(ROOT / "examples.d64"))
    args = ap.parse_args()

    c1541 = find_c1541(args.c1541)
    out = Path(args.out)

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        demo = tmp / "demo.prg"
        demo.write_bytes(build_basic(BASIC_LINES))
        readme = tmp / "readme.prg"
        readme.write_bytes(build_basic([
            (10, '?"SEE GITHUB.COM/TURRICAN128"'),
            (20, '?"/TXT2DIRART"'),
        ]))

        subprocess.run(
            [c1541, "-format", DISK_NAME, "d64", str(out),
             "-write", str(demo), "demo",
             "-write", str(readme), "readme"],
            check=True, capture_output=True)

    art = ROOT / "tools" / "examples-disk-art.txt"
    data = out.read_bytes()
    stamped, _ = txt2dirart.stamp(
        data, txt2dirart.art_from_text(art), log=lambda *a, **k: None)
    out.write_bytes(stamped)

    print(f"[*] {out}  {out.stat().st_size} B")
    print()
    txt2dirart.print_listing(stamped, txt2dirart.read_chain(bytearray(stamped))[1])
    return 0


if __name__ == "__main__":
    sys.exit(main())
