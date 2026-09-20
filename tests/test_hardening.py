"""Malformed and hostile disks, from an external code review of v1.0.

v1.0 promised "only track 18 is ever written" and "the tool never frees a
block". Both held for well-formed disks and neither held for a corrupt one:
a directory chain pointing off track 18 made the tool zero and rewrite
whatever sector it named. Reproduced against the released code with a
realistic image -- the last data sector of a real file -- before any of
this was written.
"""
import os
import sys
from pathlib import Path

import d64reader as dr
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import txt2dirart as t  # noqa: E402

ART = "----------------\n DR.J/DELYSID\n----------------\n"


def last_sector_of(data, name):
    """(track, sector) of the final data sector of a file: its link is (0, n),
    so a chain pointed at it terminates instead of wandering off."""
    e = [x for x in dr.read_directory(bytes(data)) if x.name == name][0]
    tr, se = e.track, e.sector
    while data[t.offset(tr, se)] != 0:
        o = t.offset(tr, se)
        tr, se = data[o], data[o + 1]
    return tr, se


@pytest.fixture
def corrupt(three_files):
    """Write a modified image back to the fixture path."""
    def _apply(mutate):
        data = bytearray(three_files.read_bytes())
        mutate(data)
        three_files.write_bytes(bytes(data))
        return three_files
    return _apply


# --------------------------------------------------------------------------
# 1. the directory chain must stay on track 18, sectors 1-18
# --------------------------------------------------------------------------

def test_chain_pointing_at_file_data_is_refused_and_nothing_is_written(corrupt, art_file, run_tool):
    victim = {}

    def mutate(d):
        tr, se = last_sector_of(d, "HRTRAINER")
        victim["ts"] = (tr, se)
        o = t.offset(18, 1)
        d[o], d[o + 1] = tr, se

    disk = corrupt(mutate)
    before = disk.read_bytes()
    proc = run_tool(disk, "--from-text", art_file(ART), expect_ok=False)

    assert proc.returncode == 3, "a bad image is exit 3"
    assert "track 18" in (proc.stdout + proc.stderr)
    assert disk.read_bytes() == before, "v1.0 overwrote the file's data sector here"


def test_chain_pointing_at_the_bam_is_refused(corrupt, art_file, run_tool):
    def mutate(d):
        bam = t.offset(18, 0)
        d[bam], d[bam + 1] = 0, 0xFF          # damaged BAM header: no accidental loop
        o = t.offset(18, 1)
        d[o], d[o + 1] = 18, 0

    disk = corrupt(mutate)
    before = disk.read_bytes()
    proc = run_tool(disk, "--from-text", art_file(ART), expect_ok=False)

    assert proc.returncode == 3
    assert disk.read_bytes() == before, "v1.0 wiped the BAM here"


def test_a_corrupt_chain_cannot_free_blocks(corrupt, art_file, run_tool):
    """v1.0 took this disk from 654 free blocks to 674 by zeroing the BAM."""
    def mutate(d):
        bam = t.offset(18, 0)
        d[bam], d[bam + 1] = 0, 0xFF
        o = t.offset(18, 1)
        d[o], d[o + 1] = 18, 0

    disk = corrupt(mutate)
    free_before = dr.disk_blocks_free(disk)
    run_tool(disk, "--from-text", art_file(ART), expect_ok=False)
    assert dr.disk_blocks_free(disk) == free_before


@pytest.mark.parametrize("track,sector", [(17, 0), (19, 3), (1, 0), (35, 16), (18, 0)])
def test_every_off_directory_target_is_refused(track, sector, corrupt, art_file, run_tool):
    def mutate(d):
        o = t.offset(18, 1)
        d[o], d[o + 1] = track, sector
        tgt = t.offset(track, sector)
        d[tgt], d[tgt + 1] = 0, 0xFF          # make the target terminal
    disk = corrupt(mutate)
    before = disk.read_bytes()
    run_tool(disk, "--from-text", art_file(ART), expect_ok=False)
    assert disk.read_bytes() == before


def test_a_normal_multi_sector_directory_still_works(three_files, art_file, run_tool):
    """The restriction must not break chains that legitimately grow on track 18."""
    art = art_file("".join("ROW %02d\n" % i for i in range(40)))
    run_tool(three_files, "--from-text", art, expect_ok=True)
    assert len([e for e in dr.read_directory(three_files) if e.is_art]) == 40
    run_tool(three_files, "--from-text", art_file(ART), expect_ok=True)   # and re-read


# --------------------------------------------------------------------------
# 4. an inconsistent BAM is a bad image, not a traceback
# --------------------------------------------------------------------------

def test_bam_bitmap_free_but_count_zero_is_a_controlled_refusal(corrupt, art_file, run_tool):
    def mutate(d):
        d[t.offset(18, 0) + 4 * 18] = 0        # count says 0, bitmap still says free

    disk = corrupt(mutate)
    before = disk.read_bytes()
    art = art_file("".join("ROW %02d\n" % i for i in range(40)))   # forces chain growth
    proc = run_tool(disk, "--from-text", art, expect_ok=False)

    out = proc.stdout + proc.stderr
    assert proc.returncode == 3, out
    assert "Traceback" not in out and "ValueError" not in out
    assert "BAM" in out
    assert disk.read_bytes() == before


# --------------------------------------------------------------------------
# 2 + 3. the temporary file
# --------------------------------------------------------------------------

def test_a_users_own_dot_tmp_file_is_left_alone(three_files, art_file, tmp_path, run_tool):
    """v1.0 wrote to OUT + '.tmp': a file of that name was truncated, then
    consumed by the rename."""
    out = tmp_path / "out.d64"
    mine = tmp_path / "out.d64.tmp"
    mine.write_text("MY OWN NOTES")
    run_tool(three_files, "--from-text", art_file(ART), "-o", out, expect_ok=True)
    assert mine.read_text() == "MY OWN NOTES"
    assert out.stat().st_size == 174848


def test_no_temporary_files_are_left_behind(three_files, art_file, tmp_path, run_tool):
    out = tmp_path / "out.d64"
    run_tool(three_files, "--from-text", art_file(ART), "-o", out, expect_ok=True)
    assert sorted(p.name for p in tmp_path.iterdir() if p.name.startswith(".out.d64")) == []


@pytest.mark.skipif(os.name == "nt", reason="POSIX permission bits")
def test_in_place_keeps_the_files_permissions(three_files, art_file, run_tool):
    os.chmod(three_files, 0o600)
    run_tool(three_files, "--from-text", art_file(ART), expect_ok=True)
    assert (three_files.stat().st_mode & 0o777) == 0o600


@pytest.mark.skipif(os.name == "nt", reason="symlinks need privileges on Windows")
def test_a_planted_symlink_is_not_followed(three_files, art_file, tmp_path, run_tool):
    out = tmp_path / "out.d64"
    target = tmp_path / "precious.txt"
    target.write_text("PRECIOUS")
    (tmp_path / "out.d64.tmp").symlink_to(target)
    run_tool(three_files, "--from-text", art_file(ART), "-o", out, expect_ok=True)
    assert target.read_text() == "PRECIOUS"


# --------------------------------------------------------------------------
# 5. a 1541 filename ends at the first $A0
# --------------------------------------------------------------------------

def entry(name16, kind=0x82):
    e = bytearray(32)
    e[2] = kind
    e[5:21] = name16
    return e


def test_name_ends_at_the_first_shifted_space():
    """Bytes after the first $A0 are the hidden-name trick, not part of the
    name LOAD matches. v1.0 deleted every $A0 and read this file as 'AB'."""
    assert t.entry_name(entry(b"A\xa0B" + b"\xa0" * 13)) == "A"


def test_plain_padded_name_is_unchanged():
    assert t.entry_name(entry(b"CRACKTRO" + b"\xa0" * 8)) == "CRACKTRO"


def test_a_full_sixteen_character_name_has_no_padding_to_strip():
    assert t.entry_name(entry(b"ABCDEFGHIJKLMNOP")) == "ABCDEFGHIJKLMNOP"


# --------------------------------------------------------------------------
# 6. directory growth must trust the files, not the BAM
#
# From a second external review. 1.0.1 picked new directory sectors using
# bam_is_free() alone. A BAM that marks a sector free while a file's chain
# still runs through it made the tool allocate and zero that sector: exit 0,
# no warning, file data gone. Reproduced against the shipped 1.0.1 binary.
# --------------------------------------------------------------------------

BIG_ART = "".join("ROW %02d\n" % i for i in range(40))      # forces chain growth


def put_file_sector_on_track_18(d, name, sector):
    """Extend `name`'s chain onto t18/`sector`, and have the BAM lie about it."""
    e = [x for x in dr.read_directory(bytes(d)) if x.name == name][0]
    first = t.offset(e.track, e.sector)
    d[first], d[first + 1] = t.DIR_TRACK, sector
    victim = t.offset(t.DIR_TRACK, sector)
    d[victim:victim + 256] = b"\x00\xff" + b"REAL FILE DATA" + bytes(240)
    b = t.offset(t.DIR_TRACK, 0) + 4 * t.DIR_TRACK
    d[b + 1 + sector // 8] |= (1 << (sector % 8))           # "free", but it is not
    return victim


def test_a_file_sector_on_track_18_is_never_allocated(corrupt, art_file, run_tool):
    victim = {}

    def mutate(d):
        victim["off"] = put_file_sector_on_track_18(d, "NOTE", 4)

    disk = corrupt(mutate)
    off = victim["off"]
    before = disk.read_bytes()[off:off + 256]

    run_tool(disk, "--from-text", art_file(BIG_ART), expect_ok=True)

    assert disk.read_bytes()[off:off + 256] == before, \
        "1.0.1 overwrote this file's data sector with directory entries"


def test_the_art_still_lands_when_a_sector_is_skipped(corrupt, art_file, run_tool):
    """Avoiding the occupied sector must not quietly drop rows."""
    def mutate(d):
        put_file_sector_on_track_18(d, "NOTE", 4)

    disk = corrupt(mutate)
    run_tool(disk, "--from-text", art_file(BIG_ART), expect_ok=True)
    assert len([e for e in dr.read_directory(disk) if e.is_art]) == 40


def test_the_user_is_told_a_file_is_squatting_on_track_18(corrupt, art_file, run_tool):
    def mutate(d):
        put_file_sector_on_track_18(d, "NOTE", 4)

    disk = corrupt(mutate)
    proc = run_tool(disk, "--from-text", art_file(BIG_ART), expect_ok=True)
    assert "track 18" in proc.stdout and "NOTE" in proc.stdout


def test_a_file_claiming_an_existing_directory_sector_is_refused(corrupt, art_file, run_tool):
    """t18/s1 is the directory's own first sector. A file chain through it
    means the disk contradicts itself, and stamping would zero it."""
    def mutate(d):
        put_file_sector_on_track_18(d, "NOTE", 1)

    disk = corrupt(mutate)
    before = disk.read_bytes()
    proc = run_tool(disk, "--from-text", art_file(ART), expect_ok=False)
    assert proc.returncode == 3
    assert disk.read_bytes() == before


def test_a_file_chain_that_loops_is_refused(corrupt, art_file, run_tool):
    def mutate(d):
        e = [x for x in dr.read_directory(bytes(d)) if x.name == "HRTRAINER"][0]
        o = t.offset(e.track, e.sector)
        d[o], d[o + 1] = e.track, e.sector            # points at itself

    disk = corrupt(mutate)
    before = disk.read_bytes()
    proc = run_tool(disk, "--from-text", art_file(ART), expect_ok=False)
    assert proc.returncode == 3
    assert disk.read_bytes() == before


def test_a_file_chain_pointing_off_the_disk_is_refused(corrupt, art_file, run_tool):
    def mutate(d):
        e = [x for x in dr.read_directory(bytes(d)) if x.name == "HRTRAINER"][0]
        o = t.offset(e.track, e.sector)
        d[o], d[o + 1] = 40, 0                        # track 40 on a 35-track disk

    disk = corrupt(mutate)
    before = disk.read_bytes()
    proc = run_tool(disk, "--from-text", art_file(ART), expect_ok=False)
    assert proc.returncode == 3
    assert disk.read_bytes() == before


def test_a_healthy_disk_is_unaffected_by_the_new_check(three_files, art_file, run_tool):
    """The scan must not refuse or alter anything on a normal disk."""
    proc = run_tool(three_files, "--from-text", art_file(BIG_ART), expect_ok=True)
    assert "squatting" not in proc.stdout
    assert len([e for e in dr.read_directory(three_files) if e.is_art]) == 40
    assert sorted(e.name for e in dr.real_files(three_files)) == \
        ["CRACKTRO", "HRTRAINER", "NOTE"]
