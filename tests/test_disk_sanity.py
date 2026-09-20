"""Warn when the image does not look like a disk a 1541 ever formatted.

From Alex pointing the tool at a blank lala.d64. A .d64 is just 174848
bytes and anything can produce one; a blank image walks its directory
chain perfectly well and reports no files. That reads as "the tool did
nothing" rather than "this disk is empty", which is what happened.

These are warnings, not refusals. Stamping art onto a blank disk is a
legitimate thing to want to do.
"""
import sys
from pathlib import Path

import d64reader as dr
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import txt2dirart as t  # noqa: E402

ART = "----------------\n DR.J/DELYSID\n----------------\n"


def bam_off():
    return t.offset(18, 0)


@pytest.fixture
def blank_disk(tmp_path):
    """174848 bytes of nothing. Not formatted, but structurally walkable."""
    p = tmp_path / "blank.d64"
    p.write_bytes(bytes(174848))
    return p


@pytest.fixture
def no_dos_type(tmp_path):
    """Alex's actual case: sane dir pointer and DOS version, DOS type $A0A0."""
    data = bytearray(174848)
    b = bam_off()
    data[b], data[b + 1] = 18, 1
    data[b + 2] = 0x41
    data[b + 0xA5:b + 0xA7] = b"\xa0\xa0"
    p = tmp_path / "nodostype.d64"
    p.write_bytes(bytes(data))
    return p


# --------------------------------------------------------------------------

def test_blank_disk_is_flagged(blank_disk, art_file, run_tool):
    proc = run_tool(blank_disk, "--from-text", art_file(ART), "--dry-run",
                    expect_ok=True)
    assert "does not look like it was ever formatted" in proc.stdout


def test_missing_dos_type_is_flagged(no_dos_type, art_file, run_tool):
    """The exact shape of the disk Alex hit."""
    proc = run_tool(no_dos_type, "--from-text", art_file(ART), "--dry-run",
                    expect_ok=True)
    assert "DOS type" in proc.stdout
    assert "2A" in proc.stdout


def test_an_empty_disk_says_so_in_words(blank_disk, art_file, run_tool):
    """'0 real file(s) kept' is easy to skim past."""
    proc = run_tool(blank_disk, "--from-text", art_file(ART), "--dry-run",
                    expect_ok=True)
    assert "holds no files at all" in proc.stdout


def test_a_properly_formatted_disk_gets_no_warnings(three_files, art_file, run_tool):
    """The warnings are worthless if they fire on good disks too."""
    proc = run_tool(three_files, "--from-text", art_file(ART), "--dry-run",
                    expect_ok=True)
    assert "does not look like" not in proc.stdout
    assert "holds no files at all" not in proc.stdout
    assert "DOS version" not in proc.stdout


def test_warnings_do_not_stop_the_stamp(blank_disk, art_file, run_tool):
    """A warning is not a refusal -- art-only disks are a real use."""
    run_tool(blank_disk, "--from-text", art_file(ART), "--in-place",
             expect_ok=True)
    rows = [e for e in dr.read_directory(blank_disk) if e.is_art]
    assert len(rows) == 3


def test_quiet_suppresses_the_warnings(blank_disk, art_file, tmp_path, run_tool):
    proc = run_tool(blank_disk, "--from-text", art_file(ART),
                    "-o", tmp_path / "o.d64", "--quiet", expect_ok=True)
    assert proc.stdout.strip() == ""


# --------------------------------------------------------------------------
# the property that made the "did the tool empty my disk?" question answerable
# --------------------------------------------------------------------------

def test_the_tool_can_never_free_a_block(three_files, art_file, run_tool):
    """Art allocates directory sectors. Nothing in the tool frees anything.

    This is what proves a disk that lost its files did not lose them here:
    free-block count can only stay the same or fall.
    """
    before = dr.disk_blocks_free(three_files)
    run_tool(three_files, "--from-text", art_file(ART * 8), "--in-place",
             expect_ok=True)
    after = dr.disk_blocks_free(three_files)
    assert after <= before, "stamping must never hand blocks back to the BAM"


def test_a_refusal_leaves_the_free_count_alone(three_files, art_file, run_tool):
    before = dr.disk_blocks_free(three_files)
    run_tool(three_files, "--from-text", art_file("@nope\n"), "--in-place",
             expect_ok=False)
    assert dr.disk_blocks_free(three_files) == before
