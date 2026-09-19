"""Tests for the three gaps that had to close before v1.0.

1. 40-track images were rejected outright.
2. PETSCII characters a text editor cannot type needed an external
   Windows-only tool (d64nice.exe) to fix up afterwards.
3. Every refusal was sys.exit("!! ..."), so nothing could branch on it.
"""
import shutil
from pathlib import Path

import d64reader as dr
import pytest

FIXTURES = Path(__file__).resolve().parent / "fixtures"

ART = "----------------\n DR.J/DELYSID\n----------------\n"


@pytest.fixture
def forty_track(tmp_path):
    dst = tmp_path / "forty.d64"
    shutil.copy(FIXTURES / "forty_track.d64", dst)
    return dst


# --------------------------------------------------------------------------
# gap 1 -- 40-track disks
# --------------------------------------------------------------------------

def test_forty_track_image_is_accepted(forty_track, art_file, run_tool):
    run_tool(forty_track, "--from-text", art_file(ART), "--in-place", expect_ok=True)
    art_rows = [e for e in dr.read_directory(forty_track) if e.is_art]
    assert len(art_rows) == 3


def test_forty_track_image_keeps_its_size(forty_track, art_file, run_tool):
    run_tool(forty_track, "--from-text", art_file(ART), "--in-place", expect_ok=True)
    assert forty_track.stat().st_size == 196608, "must not truncate to 35 tracks"


def test_forty_track_tracks_36_to_40_are_untouched(forty_track, art_file, run_tool):
    before = forty_track.read_bytes()
    run_tool(forty_track, "--from-text", art_file(ART), "--in-place", expect_ok=True)
    after = forty_track.read_bytes()

    start = dr.byte_offset(36, 0)
    assert before[start:] == after[start:], "the extra tracks are none of our business"


def test_forty_track_files_still_load(forty_track, art_file, run_tool):
    before = {e.name: (e.track, e.sector, e.blocks) for e in dr.real_files(forty_track)}
    run_tool(forty_track, "--from-text", art_file(ART), "--in-place", expect_ok=True)
    after = {e.name: (e.track, e.sector, e.blocks) for e in dr.real_files(forty_track)}
    assert before == after


def test_a_size_we_do_not_know_is_still_refused(tmp_path, art_file, run_tool):
    odd = tmp_path / "odd.d64"
    odd.write_bytes(b"\x00" * 180000)
    proc = run_tool(odd, "--from-text", art_file(ART), "--in-place", expect_ok=False)
    assert "not a .d64" in (proc.stdout + proc.stderr)
    # the message must tell the user what WOULD be accepted
    assert "174848" in (proc.stdout + proc.stderr)
    assert "196608" in (proc.stdout + proc.stderr)


# --------------------------------------------------------------------------
# gap 2 -- PETSCII escapes, so no external tool is ever needed
# --------------------------------------------------------------------------

def test_hex_escape_writes_the_raw_petscii_byte(three_files, art_file, run_tool):
    r"""\xa0 is shifted space -- untypeable, and the reason d64nice existed."""
    run_tool(three_files, "--from-text", art_file("\\xa0\\xa0DR.J\n"),
             "--in-place", expect_ok=True)
    row = [e for e in dr.read_directory(three_files) if e.is_art][0]
    assert row.name_exact[:2] == b"\xa0\xa0"
    assert row.name_exact[2:6] == b"DR.J"


def test_escapes_count_as_one_character_towards_the_16_limit(three_files, art_file, run_tool):
    """16 escapes is 16 bytes -- it must fit, even though it is 64 source chars."""
    run_tool(three_files, "--from-text", art_file("\\xa0" * 16 + "\n"),
             "--in-place", expect_ok=True)
    row = [e for e in dr.read_directory(three_files) if e.is_art][0]
    assert row.name_exact == b"\xa0" * 16


def test_seventeen_escaped_bytes_is_still_too_wide(three_files, art_file, run_tool):
    proc = run_tool(three_files, "--from-text", art_file("\\xa0" * 17 + "\n"),
                    "--in-place", expect_ok=False)
    assert "17 characters" in (proc.stdout + proc.stderr)


def test_escaped_bytes_are_not_uppercased(three_files, art_file, run_tool):
    r"""\x61 must stay $61, not be folded to $41 the way literal 'a' is."""
    run_tool(three_files, "--from-text", art_file("\\x61a\n"),
             "--in-place", expect_ok=True)
    row = [e for e in dr.read_directory(three_files) if e.is_art][0]
    assert row.name_exact[:2] == b"\x61A", "escape literal, plain text uppercased"


def test_double_backslash_is_a_literal_backslash(three_files, art_file, run_tool):
    run_tool(three_files, "--from-text", art_file("\\\\DR.J\n"),
             "--in-place", expect_ok=True)
    row = [e for e in dr.read_directory(three_files) if e.is_art][0]
    assert row.name_exact[:5] == b"\\DR.J"


def test_the_full_width_bar_can_be_drawn_without_any_external_tool(three_files, art_file, run_tool):
    """$a3 and $b2 are the long-line characters dir art is built from."""
    run_tool(three_files, "--from-text", art_file("\\xb2" * 16 + "\n"),
             "--in-place", expect_ok=True)
    row = [e for e in dr.read_directory(three_files) if e.is_art][0]
    assert row.name_exact == b"\xb2" * 16


def test_bad_hex_escape_is_refused_with_the_line_number(three_files, art_file, run_tool):
    proc = run_tool(three_files, "--from-text", art_file("ok\n\\xzz\n"),
                    "--in-place", expect_ok=False)
    out = proc.stdout + proc.stderr
    assert "line 2" in out and "bad hex escape" in out


def test_unknown_escape_is_refused(three_files, art_file, run_tool):
    proc = run_tool(three_files, "--from-text", art_file("\\q\n"),
                    "--in-place", expect_ok=False)
    assert "unknown escape" in (proc.stdout + proc.stderr)


def test_truncated_escape_at_end_of_line_is_refused(three_files, art_file, run_tool):
    proc = run_tool(three_files, "--from-text", art_file("DR.J\\x4\n"),
                    "--in-place", expect_ok=False)
    assert "truncated escape" in (proc.stdout + proc.stderr)


# --------------------------------------------------------------------------
# gap 3 -- exit codes, --dry-run, --version
# --------------------------------------------------------------------------

def test_success_is_exit_zero(three_files, art_file, run_tool):
    proc = run_tool(three_files, "--from-text", art_file(ART), "--in-place")
    assert proc.returncode == 0


def test_dry_run_writes_nothing(three_files, art_file, run_tool):
    original = three_files.read_bytes()
    proc = run_tool(three_files, "--from-text", art_file(ART), "--dry-run",
                    expect_ok=True)
    assert three_files.read_bytes() == original
    assert "nothing written" in proc.stdout


def test_dry_run_shows_the_listing_it_would_write(three_files, art_file, run_tool):
    proc = run_tool(three_files, "--from-text", art_file(ART), "--dry-run",
                    expect_ok=True)
    assert "DR.J/DELYSID" in proc.stdout
    assert "CRACKTRO" in proc.stdout
    assert "prg" in proc.stdout and "del" in proc.stdout


def test_dry_run_needs_no_output_flag(three_files, art_file, run_tool):
    """A preview must never be blocked by the write-destination check."""
    run_tool(three_files, "--from-text", art_file(ART), "--dry-run", expect_ok=True)


def test_version_flag(run_tool):
    proc = run_tool("--version")
    assert proc.returncode == 0
    assert "txt2dirart" in proc.stdout


def test_quiet_suppresses_progress_but_not_errors(three_files, art_file, tmp_path, run_tool):
    ok = run_tool(three_files, "--from-text", art_file(ART), "-o", tmp_path / "o.d64",
                  "--quiet", expect_ok=True)
    assert ok.stdout.strip() == ""

    bad = run_tool(three_files, "--from-text", art_file("@nope\n"),
                   "-o", tmp_path / "o2.d64", "--quiet", expect_ok=False)
    assert "matches no file" in (bad.stdout + bad.stderr)


def test_a_failed_run_leaves_no_half_written_image(three_files, art_file, tmp_path, run_tool):
    """The write is atomic: a crash must not leave a truncated .d64 behind."""
    out = tmp_path / "out.d64"
    run_tool(three_files, "--from-text", art_file("@nope\n"), "-o", out,
             expect_ok=False)
    assert not out.exists(), "no output on failure"
    assert not (tmp_path / "out.d64.tmp").exists(), "no temp file left behind"


def test_dry_run_header_shows_the_real_disk_name_and_id(three_files, art_file, run_tool):
    """The preview is only trustworthy if it names the disk it previewed."""
    proc = run_tool(three_files, "--from-text", art_file(ART), "--dry-run",
                    "-q", expect_ok=True)
    first = proc.stdout.strip().splitlines()[0]
    assert "TXT2DIRART DEMO" in first
    assert first.rstrip().endswith("DJ 2A"), "disk ID and DOS type belong on the header"


def test_blocks_is_singular_for_a_one_block_file(three_files, art_file, run_tool):
    proc = run_tool(three_files, "--from-text", art_file(ART), "--in-place",
                    expect_ok=True)
    assert "(1 block)" in proc.stdout
    assert "(3 blocks)" in proc.stdout
