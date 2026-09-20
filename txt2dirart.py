#!/usr/bin/env python3
"""txt2dirart -- stamp directory art onto a .d64 from a plain text file.

A 1541 directory listing is just a chain of 32-byte entries on track 18. If
you add entries that are closed DELs owning no sectors, the drive happily
lists them but they cost nothing and load nothing -- so the listing draws a
picture. That is the whole trick, and it is what this tool does.

What makes it worth a tool rather than a hex editor is the placement syntax:
a line of the form `@cracktro` means "put the REAL file called CRACKTRO
here", so a listing can interleave art and files freely instead of being
art-block-then-files. Any real file you do not name is appended at the end,
so a typo in the art can never silently drop a file off the disk.

    txt2dirart disk.d64 --from-text art.txt
    txt2dirart disk.d64 --from-text art.txt -o arted.d64
    txt2dirart disk.d64 --from-d64 someones-art.d64 -o arted.d64
    txt2dirart disk.d64 --from-text art.txt --dry-run

Art file format:

    ----------------      an art row, up to 16 characters
                          a blank line is a full-width blank row
    @cracktro             place the real file CRACKTRO at this point
    \\xa0\\xa0 DR.J        \\xNN writes PETSCII byte NN directly

Nothing outside track 18 is ever written. The files on the disk keep their
start sector and their length; only the listing changes.
"""
import argparse
import os
import sys

__version__ = "1.0.1"

DIR_TRACK = 18
ENTRY_SIZE = 32
ENTRIES_PER_SECTOR = 8
NAME_LEN = 16
PAD_SHIFTED = 0xA0              # CBM pads real filenames with $A0
PAD_ART = 0x20                  # ...but art rows need real spaces, see below
DIR_INTERLEAVE = 3

# Every .d64 length we accept, mapped to its track count. The odd sizes carry
# a trailing error-info block (one byte per sector); we never touch it, but we
# must not mistake it for corruption either.
D64_SIZES = {
    174848: 35,     # 35 tracks
    175531: 35,     # 35 tracks + error info
    196608: 40,     # 40 tracks
    197376: 40,     # 40 tracks + error info
}


# --------------------------------------------------------------------------
# errors -- one class per exit code, so scripts can branch on what went wrong
# --------------------------------------------------------------------------

class DirArtError(Exception):
    """Base for every refusal. `code` becomes the process exit status."""
    code = 1


class BadImage(DirArtError):
    """The .d64 is not a shape we can work with."""
    code = 3


class BadArt(DirArtError):
    """The art file does not parse."""
    code = 4


class TokenNotFound(DirArtError):
    """An @token names a file that is not on the disk."""
    code = 5


class NoRoom(DirArtError):
    """Track 18 cannot hold this many entries."""
    code = 6


# --------------------------------------------------------------------------
# 1541 geometry
# --------------------------------------------------------------------------

def sectors_on(track):
    """Sectors in a track. Zones are the same on 35- and 40-track disks."""
    if track <= 17:
        return 21
    if track <= 24:
        return 19
    if track <= 30:
        return 18
    return 17


def offset(track, sector):
    """Byte offset of a sector, counted from track 1 sector 0."""
    n = sum(sectors_on(t) for t in range(1, track))
    return (n + sector) * 256


def track_count(data):
    """Track count for this image, or refuse it."""
    size = len(data)
    if size not in D64_SIZES:
        known = ", ".join(str(s) for s in sorted(D64_SIZES))
        raise BadImage(
            f"{size} bytes is not a .d64 -- expected one of: {known} "
            f"(35 or 40 tracks, with or without error info)")
    return D64_SIZES[size]


# --------------------------------------------------------------------------
# reading the directory
# --------------------------------------------------------------------------

def read_chain(d):
    """Walk track 18's chain, returning [(track, sector), ...] and its entries."""
    chain, entries = [], []
    t, s = DIR_TRACK, 1
    seen = set()
    while t:
        if (t, s) in seen:
            raise BadImage("directory chain loops -- refusing to touch this disk")
        # Every sector in this chain gets zeroed and rewritten by stamp(), so
        # the chain is only trusted while it stays where a directory lives:
        # track 18, sectors 1-18. Sector 0 is the BAM. "Somewhere on the disk"
        # is not good enough -- v1.0 checked only that, and a corrupt link to
        # t17/s13 made it overwrite the last data sector of a real file.
        if t != DIR_TRACK or not 1 <= s < sectors_on(DIR_TRACK):
            raise BadImage(
                f"directory chain points at t{t}/s{s}; directory sectors must be "
                f"track {DIR_TRACK}, sectors 1-{sectors_on(DIR_TRACK) - 1}. This "
                f"disk's directory is damaged or non-standard -- refusing to touch it")
        seen.add((t, s))
        chain.append((t, s))
        base = offset(t, s)
        for i in range(ENTRIES_PER_SECTOR):
            e = bytearray(d[base + i * ENTRY_SIZE: base + (i + 1) * ENTRY_SIZE])
            if e[2]:                       # byte 2 = file type; 0 = slot never used
                e[0] = e[1] = 0            # strip the link bytes off entry 0
                entries.append(e)
        t, s = d[base], d[base + 1]
    return chain, entries


def is_art_entry(e):
    """Art rows are DELs that own no block. Real files are everything else."""
    return (e[2] & 0x0F) == 0 and (e[30] | e[31]) == 0


def entry_name(e):
    """The name an @token is matched against: what LOAD would match.

    A 1541 filename ends at the first $A0. Anything after it is the hidden-name
    trick, shown after the closing quote in a listing but not part of the name.
    v1.0 deleted every $A0 instead, so the file A,$A0,B read as "AB" and an
    @ab token could land on the wrong file.

    Trailing spaces are still dropped, on purpose: a token comes from a text
    file, where trailing whitespace is invisible and usually an accident, so
    "AB " on the disk answers to @ab. If a disk holds both "AB" and "AB ",
    repeated @ab tokens place them in directory order.
    """
    raw = bytes(e[5:NAME_LEN + 5])
    cut = raw.find(bytes([PAD_SHIFTED]))
    if cut != -1:
        raw = raw[:cut]
    return raw.rstrip(b" ").decode("latin1").upper()


def display_name(e):
    """The 16 name bytes rendered for a --dry-run listing."""
    raw = bytes(e[5:NAME_LEN + 5]).replace(bytes([PAD_SHIFTED]), b" ")
    return "".join(chr(b) if 32 <= b < 127 else "." for b in raw)


# --------------------------------------------------------------------------
# building entries
# --------------------------------------------------------------------------

def make_art_entry(name_bytes, pad=PAD_ART):
    e = bytearray(ENTRY_SIZE)
    e[2] = 0x80                            # closed DEL
    e[3] = e[4] = 0                        # owns no data block
    e[5:5 + NAME_LEN] = name_bytes[:NAME_LEN].ljust(NAME_LEN, bytes([pad]))
    return e


def unescape(line):
    r"""Turn an art line into exactly the bytes to store.

    Plain text is uppercased -- the C64's default charset has no lowercase,
    so lowercase input would otherwise come out as graphics characters. But
    \xNN escapes are taken literally, which is how you reach the PETSCII
    codes a text editor cannot type: the full-width bar, the corner pieces,
    shifted space ($A0). \\ is a literal backslash.

    Returns the byte string; raises BadArt on a malformed escape.
    """
    out = bytearray()
    i = 0
    while i < len(line):
        b = line[i:i + 1]
        if b != b"\\":
            out += b.upper()
            i += 1
            continue
        nxt = line[i + 1:i + 2]
        if nxt == b"\\":
            out += b"\\"
            i += 2
        elif nxt in (b"x", b"X"):
            digits = line[i + 2:i + 4]
            if len(digits) < 2:
                raise BadArt(rf"truncated escape at end of line: {line.decode('latin1')!r}")
            try:
                out.append(int(digits, 16))
            except ValueError:
                raise BadArt(
                    rf"bad hex escape \x{digits.decode('latin1')} "
                    rf"in line {line.decode('latin1')!r}")
            i += 4
        else:
            raise BadArt(
                rf"unknown escape \{nxt.decode('latin1')} "
                rf"in line {line.decode('latin1')!r} (use \\ for a literal backslash)")
    return bytes(out)


def art_from_text(path):
    """Parse an art file into art entries and '@name' placement tokens."""
    try:
        with open(path, "rb") as fh:
            raw = fh.read()
    except OSError as exc:
        raise BadArt(f"cannot read art file: {exc}")

    out = []
    for lineno, raw_line in enumerate(raw.split(b"\n"), 1):
        line = raw_line.rstrip(b"\r")
        if line.startswith(b"@"):
            out.append("@" + line[1:].strip().decode("latin1").upper())
            continue
        try:
            cooked = unescape(line)
        except BadArt as exc:
            raise BadArt(f"line {lineno}: {exc}")
        if len(cooked) > NAME_LEN:
            raise BadArt(
                f"line {lineno}: {len(cooked)} characters, but a directory entry "
                f"holds {NAME_LEN}: {line.decode('latin1')!r}")
        # Art rows are padded with real spaces, not $A0: a row of $A0 lists as
        # an empty name ("") instead of the full-width blank line you drew.
        out.append(make_art_entry(cooked, pad=PAD_ART))

    while out and isinstance(out[-1], bytearray) and out[-1][5:5 + NAME_LEN] == b" " * NAME_LEN:
        out.pop()                                       # trailing blanks are noise
    return out


def art_from_d64(path):
    """Lift the entry names off another disk and reuse them as art."""
    try:
        with open(path, "rb") as fh:
            d = fh.read()
    except OSError as exc:
        raise BadArt(f"cannot read source .d64: {exc}")
    track_count(d)
    _, entries = read_chain(d)
    return [make_art_entry(bytes(e[5:5 + NAME_LEN]), pad=PAD_ART) for e in entries]


# --------------------------------------------------------------------------
# placement
# --------------------------------------------------------------------------

def check_tokens(art, real):
    """Validate every @token before placing anything.

    Reporting only the first bad token turns fixing an art file into one
    round trip per mistake: run, fix one name, run again, find the next.
    An art file written for one disk and pointed at another is the normal
    case -- the tokens name files, and a different disk has different
    files -- so every wrong name is reported together.
    """
    available = [entry_name(e) for e in real]
    remaining = list(available)
    missing, exhausted = [], []
    for item in art:
        if not isinstance(item, str):
            continue
        want = item[1:]
        if want in remaining:
            remaining.remove(want)
        elif want in available:
            exhausted.append(want)          # named more times than it exists
        else:
            missing.append(want)

    if not missing and not exhausted:
        return

    have = ", ".join(available) or "no files at all"
    lines = []
    if missing:
        names = ", ".join("@" + m for m in dict.fromkeys(missing))
        lines.append(f"{len(dict.fromkeys(missing))} token(s) match no file "
                     f"on the disk: {names}")
    for want in dict.fromkeys(exhausted):
        lines.append(f"@{want} appears more times in the art than the disk has "
                     f"copies of {want}")
    lines.append(f"the disk contains: {have}")
    lines.append("a token names a file on THIS disk, so art written for another "
                 "disk needs its tokens renamed")
    raise TokenNotFound("\n   ".join(lines))


def place(art, real, log=print):
    """Interleave the real files into the art according to '@name' tokens."""
    check_tokens(art, real)
    pool = list(real)
    entries = []
    for item in art:
        if not isinstance(item, str):
            entries.append(item)
            continue
        want = item[1:]
        match = next(e for e in pool if entry_name(e) == want)
        pool.remove(match)
        entries.append(match)
        log(f"    placed  {want!r} where @{want} appears")
    if pool:
        log(f"[!] {len(pool)} file(s) not named by a token -- appended at the end: "
            + ", ".join(entry_name(e) for e in pool))
        entries.extend(pool)
    return entries


# --------------------------------------------------------------------------
# BAM
# --------------------------------------------------------------------------

def format_warnings(d):
    """Reasons to doubt this image was ever formatted by a 1541.

    A .d64 is just 174848 bytes; anything can produce one. A blank image
    walks its directory chain perfectly well and reports no files, which
    reads as "the tool did nothing" rather than "this disk is empty".
    These are warnings and not refusals -- stamping art onto a blank disk
    is a legitimate thing to want -- but they should be said out loud.
    """
    bam = offset(DIR_TRACK, 0)
    out = []
    if bytes(d[bam + 0xA5:bam + 0xA7]) != b"2A":
        got = bytes(d[bam + 0xA5:bam + 0xA7])
        out.append(f"DOS type is {got!r}, not b'2A' -- this image does not look "
                   f"like it was ever formatted")
    if d[bam + 2] != 0x41:
        out.append(f"DOS version byte is ${d[bam + 2]:02X}, not $41 ('A')")
    if (d[bam], d[bam + 1]) != (DIR_TRACK, 1):
        out.append(f"the BAM points its first directory sector at "
                   f"t{d[bam]}/s{d[bam + 1]}, not t{DIR_TRACK}/s1")
    return out


def bam_free(d, track):
    return d[offset(DIR_TRACK, 0) + 4 * track]


def bam_is_free(d, track, sector):
    b = offset(DIR_TRACK, 0) + 4 * track
    return bool(d[b + 1 + sector // 8] & (1 << (sector % 8)))


def bam_allocate(d, track, sector):
    b = offset(DIR_TRACK, 0) + 4 * track
    if d[b + 1 + sector // 8] & (1 << (sector % 8)):
        if d[b] == 0:
            # The bitmap and the free count disagree. Decrementing would raise
            # a bare ValueError out of a bytearray; this is a damaged disk and
            # should be reported as one.
            raise BadImage(
                f"BAM is inconsistent on track {track}: sector {sector} is marked "
                f"free but the track's free count is zero")
        d[b + 1 + sector // 8] &= ~(1 << (sector % 8)) & 0xFF
        d[b] -= 1


# --------------------------------------------------------------------------
# the stamp itself
# --------------------------------------------------------------------------

def stamp(data, art, file_first=False, log=print):
    """Return a new image with `art` stamped onto it. `data` is not modified."""
    d = bytearray(data)
    track_count(d)

    for problem in format_warnings(d):
        log(f"[!] {problem}")

    chain, live = read_chain(d)
    real = [e for e in live if not is_art_entry(e)]
    tokens = [x for x in art if isinstance(x, str)]

    log(f"[*] {len(real)} real file(s) kept, {len(art) - len(tokens)} art rows"
        + (f", {len(tokens)} placement token(s)" if tokens else ""))
    if not real:
        log("[!] this disk holds no files at all -- the listing will be art "
            "and nothing else")
    for e in real:
        n = e[30] + e[31] * 256
        log(f"    keeping {entry_name(e)!r} ({n} block{'' if n == 1 else 's'})")

    if tokens:
        entries = place(art, real, log=log)
    else:
        entries = (real + art) if file_first else (art + real)

    need = max(1, (len(entries) + ENTRIES_PER_SECTOR - 1) // ENTRIES_PER_SECTOR)
    while len(chain) < need:
        last_s = chain[-1][1]
        span = sectors_on(DIR_TRACK)
        cand = [(last_s + DIR_INTERLEAVE + i) % span for i in range(span)]
        nxt = next((s for s in cand if s and (DIR_TRACK, s) not in chain
                    and bam_is_free(d, DIR_TRACK, s)), None)
        if nxt is None:
            raise NoRoom(
                f"track {DIR_TRACK} is full -- {len(entries)} entries need "
                f"{need} sectors, and only {len(chain)} are available")
        chain.append((DIR_TRACK, nxt))
        bam_allocate(d, DIR_TRACK, nxt)

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

    log(f"[*] {len(chain)} directory sector(s) on track {DIR_TRACK}, "
        f"{bam_free(d, DIR_TRACK)} free there")
    return bytes(d), entries


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def build_parser():
    p = argparse.ArgumentParser(
        prog="txt2dirart",
        description="Stamp C64 directory art onto a .d64 from a plain text file.",
        epilog="Art file: one line per row, up to 16 chars. '@name' places a real "
               r"file there. '\xNN' writes PETSCII byte NN.",
    )
    p.add_argument("d64", help="the disk image to stamp")
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--from-text", dest="src_text", metavar="ART.TXT",
                     help="art file, one line per directory row")
    src.add_argument("--from-d64", dest="src_d64", metavar="ART.D64",
                     help="lift the art off another disk's listing")
    dest = p.add_mutually_exclusive_group()
    dest.add_argument("-o", "--out", metavar="OUT.D64",
                      help="write the result to a new file instead of the input")
    dest.add_argument("--in-place", action="store_true",
                      help="overwrite the input image (this is the default; the "
                           "flag exists so a build script can say so explicitly)")
    p.add_argument("--file-first", action="store_true",
                   help="put the real files above the art (default: art first)")
    p.add_argument("--dry-run", action="store_true",
                   help="print the listing that would be written, and stop")
    p.add_argument("-q", "--quiet", action="store_true", help="only report problems")
    p.add_argument("--version", action="version", version=f"txt2dirart {__version__}")
    return p


def petscii_str(raw):
    """Render raw name bytes for a terminal, $A0 padding shown as spaces."""
    return "".join(chr(b) if 32 <= b < 127 else "." for b in
                   bytes(raw).replace(bytes([PAD_SHIFTED]), b" "))


def print_listing(d, entries):
    """Print what a LIST would show, header line and all."""
    bam = offset(DIR_TRACK, 0)
    name = petscii_str(d[bam + 0x90:bam + 0xA0])
    disk_id = petscii_str(d[bam + 0xA2:bam + 0xA4])
    dos = petscii_str(d[bam + 0xA5:bam + 0xA7])
    print()
    print(f'    0 "{name}" {disk_id} {dos}')
    for e in entries:
        blocks = e[30] + e[31] * 256
        kind = "del" if is_art_entry(e) else {1: "seq", 2: "prg", 3: "usr", 4: "rel"}.get(
            e[2] & 0x0F, "prg")
        print(f'{blocks:5} "{display_name(e)}" {kind}')
    print()


def main(argv=None):
    args = build_parser().parse_args(argv)
    log = (lambda *a, **k: None) if args.quiet else print

    # Stamping the disk you named is the default; -o writes elsewhere instead.
    # In-place is safe to default to because only track 18 is ever rewritten:
    # every file keeps its start sector and its length, so the worst outcome
    # is a listing you do not like, and that is fixed by stamping again.

    try:
        with open(args.d64, "rb") as fh:
            data = fh.read()
    except OSError as exc:
        raise BadImage(f"cannot read {args.d64}: {exc}")

    art = art_from_d64(args.src_d64) if args.src_d64 else art_from_text(args.src_text)
    result, entries = stamp(data, art, file_first=args.file_first, log=log)

    if args.dry_run:
        print_listing(result, entries)
        log("[*] dry run -- nothing written")
        return 0

    out = args.out or args.d64
    write_atomically(out, result)
    log(f"[*] DONE -> {out}")
    return 0


def write_atomically(out, data):
    """Write `data` to `out` so that a crash can never leave half a disk image.

    The temporary file is created with O_EXCL under a random name. O_EXCL
    refuses an existing path and never follows a symlink, so neither a file
    the user happens to own nor a link someone planted can be written through.
    v1.0 used OUT + ".tmp", opened with "wb": a file of that name was silently
    truncated and then consumed by the rename.

    This is deliberately not tempfile.mkstemp(): the tool imports argparse, os
    and sys and nothing else, and the release build's module exclusions are
    tuned to exactly that.
    """
    folder = os.path.dirname(os.path.abspath(out))
    try:
        mode = os.stat(out).st_mode & 0o7777       # replacing a file: keep its permissions
    except OSError:
        umask = os.umask(0)                        # new file: what open() would have given
        os.umask(umask)
        mode = 0o666 & ~umask

    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
    for _ in range(16):
        tmp = os.path.join(
            folder, "." + os.path.basename(out) + "." + os.urandom(6).hex() + ".tmp")
        try:
            fd = os.open(tmp, flags, 0o600)
            break
        except FileExistsError:
            continue
    else:
        raise DirArtError(f"could not create a temporary file next to {out}")

    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        os.chmod(tmp, mode)
        os.replace(tmp, out)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


if __name__ == "__main__":
    try:
        sys.exit(main())
    except DirArtError as exc:
        # stdout is block-buffered when piped and stderr is not, so without
        # this flush the error jumps ahead of the progress lines that explain
        # what the tool was doing when it hit the problem.
        sys.stdout.flush()
        print(f"!! {exc}", file=sys.stderr)
        sys.exit(exc.code)
    except KeyboardInterrupt:
        sys.exit(130)
