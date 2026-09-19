"""A deliberately independent .d64 directory reader, for use by the tests only.

txt2dirart must not be allowed to grade its own homework: if the round-trip
test read the directory back with the tool's own read_chain(), a bug in the
sector-offset maths would cancel itself out and the test would still pass.
So this module re-derives the layout from the 1541 docs by itself, in a
different style, and the tests compare the two.

It is intentionally read-only and intentionally dumb.
"""

SECTOR_COUNTS = [
    (1, 17, 21),
    (18, 24, 19),
    (25, 30, 18),
    (31, 40, 17),
]

FILE_TYPES = {0: "del", 1: "seq", 2: "prg", 3: "usr", 4: "rel"}


def sectors_in_track(track):
    for lo, hi, n in SECTOR_COUNTS:
        if lo <= track <= hi:
            return n
    raise ValueError(f"track {track} out of range")


def byte_offset(track, sector):
    """Linear offset of (track, sector), counted the long way round."""
    total = 0
    for t in range(1, track):
        total += sectors_in_track(t)
    return (total + sector) * 256


class Entry:
    def __init__(self, raw):
        self.raw = bytes(raw)
        self.type_byte = self.raw[2]
        self.closed = bool(self.type_byte & 0x80)
        self.kind = FILE_TYPES.get(self.type_byte & 0x0F, "?")
        self.track = self.raw[3]
        self.sector = self.raw[4]
        self.name_raw = self.raw[5:21]
        self.blocks = self.raw[30] + self.raw[31] * 256

    @property
    def is_art(self):
        """Art rows are closed DELs owning no block."""
        return (self.type_byte & 0x0F) == 0 and self.blocks == 0

    @property
    def name(self):
        """Name with CBM's $A0 padding stripped, trailing spaces kept."""
        return self.name_raw.rstrip(b"\xa0").decode("latin1")

    @property
    def name_exact(self):
        """All 16 bytes, nothing stripped -- for byte-level assertions."""
        return self.name_raw

    def __repr__(self):
        return f"<Entry {self.kind} {self.name!r} {self.blocks} blocks>"


def read_directory(path_or_bytes):
    """Walk track 18's chain and return every in-use entry, in listing order."""
    if isinstance(path_or_bytes, (bytes, bytearray)):
        data = bytes(path_or_bytes)
    else:
        with open(path_or_bytes, "rb") as fh:
            data = fh.read()

    entries = []
    track, sector = 18, 1
    visited = set()
    while track:
        if (track, sector) in visited:
            raise ValueError("directory chain loops")
        visited.add((track, sector))
        base = byte_offset(track, sector)
        block = data[base:base + 256]
        if len(block) < 256:
            raise ValueError(f"image too short for t{track}/s{sector}")
        for i in range(8):
            raw = block[i * 32:(i + 1) * 32]
            if raw[2]:                       # type byte 0 == slot never used
                entries.append(Entry(raw))
        track, sector = block[0], block[1]
    return entries


def listing(path_or_bytes):
    """Just the names, the way a LIST would show them."""
    return [e.name for e in read_directory(path_or_bytes)]


def real_files(path_or_bytes):
    """Entries that are actual files (not art rows)."""
    return [e for e in read_directory(path_or_bytes) if not e.is_art]


def disk_blocks_free(path_or_bytes):
    if isinstance(path_or_bytes, (bytes, bytearray)):
        data = bytes(path_or_bytes)
    else:
        with open(path_or_bytes, "rb") as fh:
            data = fh.read()
    bam = byte_offset(18, 0)
    total = 0
    for t in range(1, 36):
        if t == 18:
            continue
        total += data[bam + 4 * t]
    return total
