#!/usr/bin/env python3
"""Stamp directory art onto a .d64 without touching its files.

The crack disk is mastered by c1541 (format + write one prg), which has no
dir-art support, and we are not a Sparkle production so the .sls "DirArt:"
route is not available either. This does the same job directly: it rewrites
track 18's directory chain as [art entries] + [the real files], so the
listing draws a picture and HRTRAINER still loads.

Art entries are closed-DEL ($80) with 0 blocks -- the drive lists them but
they own no sectors, which is the standard dir-art trick.

Art sources:
  --from-d64 art.d64    copy the entry names out of a dir-art disk
                        (DirMaster output, or Arok's green_dirart.d64)
  --from-text art.txt   one line per entry, <=16 chars, blank line = blank row

Usage:
  python dirart.py out/hr_trainer.d64 --from-text dirart.txt
  python dirart.py out/hr_trainer.d64 --from-d64 green_dirart.d64 -o arted.d64

Run d64nice.exe afterwards if the art uses '|' or the long-line PETSCII char.
"""
import argparse, os, sys

DIR_TRACK = 18
ENTRY_SIZE = 32
ENTRIES_PER_SECTOR = 8
PAD = 0xA0                      # CBM pads filenames with $A0, not spaces


def sectors_on(track):
    if track <= 17: return 21
    if track <= 24: return 19
    if track <= 30: return 18
    return 17


def offset(track, sector):
    n = sum(sectors_on(t) for t in range(1, track))
    return (n + sector) * 256


def read_chain(d):
    """Walk the directory chain, returning [(track,sector), ...] and all live entries."""
    chain, entries = [], []
    t, s = DIR_TRACK, 1
    seen = set()
    while t:
        if (t, s) in seen:
            sys.exit("!! directory chain loops -- refusing to touch this disk")
        seen.add((t, s))
        chain.append((t, s))
        base = offset(t, s)
        for i in range(ENTRIES_PER_SECTOR):
            e = bytearray(d[base + i * ENTRY_SIZE: base + (i + 1) * ENTRY_SIZE])
            if e[2]:                       # byte 2 = file type; 0 = never used
                e[0] = e[1] = 0            # strip the link bytes off entry 0
                entries.append(e)
        t, s = d[base], d[base + 1]
    return chain, entries


def make_art_entry(name_bytes, pad=PAD):
    e = bytearray(ENTRY_SIZE)
    e[2] = 0x80                            # closed DEL
    e[3] = e[4] = 0                        # owns no data block
    e[5:21] = name_bytes[:16].ljust(16, bytes([pad]))
    return e


def art_from_d64(path):
    d = open(path, "rb").read()
    _, entries = read_chain(d)
    return [make_art_entry(bytes(e[5:21])) for e in entries]


def art_from_text(path):
    """Art rows, plus optional '@name' placement tokens.

    A line of the form  @cracktro  is not art -- it means "put the REAL file
    called CRACKTRO here". That is what lets a listing interleave files and art
    freely, e.g. file / separator / file / separator / art. Any real file not
    named by a token is appended at the end, so a file can never be dropped by
    a typo in the art.
    """
    out = []
    with open(path, "rb") as fh:
        for raw in fh.read().split(b"\n"):
            line = raw.rstrip(b"\r")
            if line.startswith(b"@"):
                out.append("@" + line[1:].strip().decode("latin1").upper())
                continue
            if len(line) > 16:
                sys.exit(f"!! art line longer than 16 chars: {line!r}")
            # pad art rows with real spaces, not $A0: a row of $A0 lists as an
            # empty name ("") instead of a full-width blank line
            out.append(make_art_entry(line.upper(), pad=0x20))
    while out and isinstance(out[-1], bytearray) and out[-1][5:21] == b" " * 16:
        out.pop()                                       # drop trailing blank rows
    return out


def entry_name(e):
    return bytes(e[5:21]).replace(bytes([PAD]), b"").rstrip().decode("latin1").upper()


def place(art, real):
    """Interleave real files into the art according to '@name' tokens."""
    pool = list(real)
    entries = []
    for item in art:
        if not isinstance(item, str):
            entries.append(item); continue
        want = item[1:]
        m = next((e for e in pool if entry_name(e) == want), None)
        if m is None:
            sys.exit(f"!! dirart token @{want} matches no file on the disk "
                     f"(disk has: {', '.join(entry_name(e) for e in pool) or 'nothing'})")
        pool.remove(m); entries.append(m)
        print(f"    placed  {want!r} where @{want} appears")
    if pool:
        print(f"[!] {len(pool)} file(s) not named by a token -- appended at the end: "
              + ", ".join(entry_name(e) for e in pool))
        entries.extend(pool)
    return entries


def bam_free(d, track):
    return d[offset(DIR_TRACK, 0) + 4 * track]


def bam_is_free(d, track, sector):
    b = offset(DIR_TRACK, 0) + 4 * track
    return bool(d[b + 1 + sector // 8] & (1 << (sector % 8)))


def bam_allocate(d, track, sector):
    b = offset(DIR_TRACK, 0) + 4 * track
    if d[b + 1 + sector // 8] & (1 << (sector % 8)):
        d[b + 1 + sector // 8] &= ~(1 << (sector % 8)) & 0xFF
        d[b] -= 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("d64")
    ap.add_argument("--from-d64", dest="src_d64")
    ap.add_argument("--from-text", dest="src_text")
    ap.add_argument("-o", "--out", help="write here instead of in place")
    ap.add_argument("--file-first", action="store_true",
                    help="put the real files above the art (default: art first)")
    args = ap.parse_args()
    if bool(args.src_d64) == bool(args.src_text):
        sys.exit("!! pick exactly one of --from-d64 / --from-text")

    d = bytearray(open(args.d64, "rb").read())
    if len(d) < 174848:
        sys.exit(f"!! {args.d64}: {len(d)} B -- not a 35-track d64")

    chain, live = read_chain(d)
    real = [e for e in live if (e[2] & 0x0F) != 0]     # DEL entries are art, keep the rest
    art = art_from_d64(args.src_d64) if args.src_d64 else art_from_text(args.src_text)
    tokens = [x for x in art if isinstance(x, str)]
    print(f"[*] {len(real)} real file(s) kept, {len(art) - len(tokens)} art rows"
          + (f", {len(tokens)} placement token(s)" if tokens else ""))
    for e in real:
        print(f"    keeping {entry_name(e)!r} ({e[30] + e[31] * 256} blocks)")
    if tokens:
        entries = place(art, real)
    else:
        entries = (real + art) if args.file_first else (art + real)

    need = max(1, (len(entries) + ENTRIES_PER_SECTOR - 1) // ENTRIES_PER_SECTOR)
    # grow the chain on track 18 with the usual interleave of 3
    while len(chain) < need:
        last_s = chain[-1][1]
        cand = [(last_s + 3 + i) % sectors_on(DIR_TRACK) for i in range(sectors_on(DIR_TRACK))]
        nxt = next((s for s in cand if s and (DIR_TRACK, s) not in chain
                    and bam_is_free(d, DIR_TRACK, s)), None)
        if nxt is None:
            sys.exit(f"!! track 18 is full -- {len(entries)} entries need {need} sectors")
        chain.append((DIR_TRACK, nxt))
        bam_allocate(d, DIR_TRACK, nxt)

    # rewrite every sector in the chain
    for idx, (t, s) in enumerate(chain):
        base = offset(t, s)
        d[base:base + 256] = bytes(256)
        last = idx == len(chain) - 1
        d[base] = 0 if last else chain[idx + 1][0]
        d[base + 1] = 0xFF if last else chain[idx + 1][1]
        for i in range(ENTRIES_PER_SECTOR):
            n = idx * ENTRIES_PER_SECTOR + i
            if n >= len(entries):
                break
            e = bytearray(entries[n])
            if i == 0:                      # entry 0 shares its first 2 bytes with the link
                e[0], e[1] = d[base], d[base + 1]
            d[base + i * ENTRY_SIZE: base + (i + 1) * ENTRY_SIZE] = e

    out = args.out or args.d64
    open(out, "wb").write(bytes(d))
    print(f"[*] {len(chain)} directory sector(s) on track 18, {bam_free(d, DIR_TRACK)} free there")
    print(f"[*] DONE -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
