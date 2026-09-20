"""Characterization tests: what the tool does today, locked down.

These were written before any refactoring, so that closing the known gaps
(40-track images, PETSCII escapes, exit codes) cannot silently change
behaviour that already worked.
"""
import d64reader as dr
import pytest

SIMPLE_ART = """\
----------------
 dr.j presents
----------------
"""

TOKEN_ART = """\
----------------
 dr.j presents
----------------
@cracktro
@hrtrainer
----------------
"""


def names(path):
    return [e.name_exact for e in dr.read_directory(path)]


# --------------------------------------------------------------------------
# the basic job
# --------------------------------------------------------------------------

def test_art_rows_appear_above_the_files(three_files, art_file, run_tool):
    art = art_file(SIMPLE_ART)
    run_tool(three_files, "--from-text", art, "--in-place", expect_ok=True)

    entries = dr.read_directory(three_files)
    art_rows = [e for e in entries if e.is_art]
    files = [e for e in entries if not e.is_art]

    assert len(art_rows) == 3, "three art lines in, three art rows out"
    assert [e.name for e in files] == ["CRACKTRO", "HRTRAINER", "NOTE"]
    # art first is the default
    assert entries[0].is_art and entries[3].name == "CRACKTRO"


def test_art_text_is_uppercased_and_space_padded(three_files, art_file, run_tool):
    run_tool(three_files, "--from-text", art_file(SIMPLE_ART), "--in-place", expect_ok=True)
    art_rows = [e for e in dr.read_directory(three_files) if e.is_art]

    assert art_rows[0].name_exact == b"----------------"
    # uppercased, and padded with real spaces ($20) -- NOT $A0, which would
    # list as an empty name instead of a full-width row
    assert art_rows[1].name_exact == b" DR.J PRESENTS  "
    assert b"\xa0" not in art_rows[1].name_exact


def test_art_rows_own_no_sectors(three_files, art_file, run_tool):
    run_tool(three_files, "--from-text", art_file(SIMPLE_ART), "--in-place", expect_ok=True)
    for e in dr.read_directory(three_files):
        if e.is_art:
            assert e.blocks == 0, "art must not claim blocks"
            assert e.type_byte == 0x80, "art rows are closed DEL"


# --------------------------------------------------------------------------
# the invariant that matters most: the files must still be loadable
# --------------------------------------------------------------------------

def test_files_keep_their_start_sector_and_size(three_files, art_file, run_tool):
    before = {e.name: (e.track, e.sector, e.blocks) for e in dr.real_files(three_files)}
    run_tool(three_files, "--from-text", art_file(SIMPLE_ART), "--in-place", expect_ok=True)
    after = {e.name: (e.track, e.sector, e.blocks) for e in dr.real_files(three_files)}

    assert before == after, "stamping art must not move or resize any file"
    assert set(before) == {"CRACKTRO", "HRTRAINER", "NOTE"}


def test_file_payload_bytes_are_untouched(three_files, art_file, run_tool):
    original = three_files.read_bytes()
    run_tool(three_files, "--from-text", art_file(SIMPLE_ART), "--in-place", expect_ok=True)
    stamped = three_files.read_bytes()

    # every sector outside track 18 must be byte-identical
    for track in list(range(1, 18)) + list(range(19, 36)):
        for sector in range(dr.sectors_in_track(track)):
            off = dr.byte_offset(track, sector)
            assert original[off:off + 256] == stamped[off:off + 256], \
                f"t{track}/s{sector} changed but only track 18 should"


def test_no_file_is_ever_dropped(three_files, art_file, run_tool):
    """Art that names only one file must still keep the other two."""
    art = art_file("----------------\n@cracktro\n----------------\n")
    proc = run_tool(three_files, "--from-text", art, "--in-place", expect_ok=True)

    listed = [e.name for e in dr.real_files(three_files)]
    assert sorted(listed) == ["CRACKTRO", "HRTRAINER", "NOTE"]
    assert "appended at the end" in proc.stdout


# --------------------------------------------------------------------------
# @token placement
# --------------------------------------------------------------------------

def test_tokens_interleave_files_into_the_art(three_files, art_file, run_tool):
    run_tool(three_files, "--from-text", art_file(TOKEN_ART), "--in-place", expect_ok=True)
    entries = dr.read_directory(three_files)

    kinds = [("art" if e.is_art else e.name) for e in entries]
    assert kinds == ["art", "art", "art", "CRACKTRO", "HRTRAINER", "art", "NOTE"]


def test_token_is_case_insensitive(three_files, art_file, run_tool):
    run_tool(three_files, "--from-text",
             art_file("@CrAcKtRo\n----------------\n"), "--in-place", expect_ok=True)
    entries = dr.read_directory(three_files)
    assert entries[0].name == "CRACKTRO"


# --------------------------------------------------------------------------
# ordering switches
# --------------------------------------------------------------------------

def test_file_first_puts_the_files_above_the_art(three_files, art_file, run_tool):
    run_tool(three_files, "--from-text", art_file(SIMPLE_ART),
             "--file-first", "--in-place", expect_ok=True)
    entries = dr.read_directory(three_files)
    assert not entries[0].is_art
    assert entries[0].name == "CRACKTRO"
    assert entries[-1].is_art


# --------------------------------------------------------------------------
# input handling
# --------------------------------------------------------------------------

def test_trailing_blank_rows_are_dropped(three_files, art_file, run_tool):
    run_tool(three_files, "--from-text",
             art_file("----------------\n\n\n\n"), "--in-place", expect_ok=True)
    art_rows = [e for e in dr.read_directory(three_files) if e.is_art]
    assert len(art_rows) == 1, "blank rows at the end are noise, not art"


def test_interior_blank_row_is_kept_as_a_full_width_blank(three_files, art_file, run_tool):
    run_tool(three_files, "--from-text",
             art_file("----------------\n\n----------------\n"), "--in-place", expect_ok=True)
    art_rows = [e for e in dr.read_directory(three_files) if e.is_art]
    assert len(art_rows) == 3
    assert art_rows[1].name_exact == b" " * 16


def test_crlf_art_files_work(three_files, art_file, run_tool):
    """Art written on Windows must behave the same as art written on Linux."""
    run_tool(three_files, "--from-text",
             art_file(b"----------------\r\n DR.J\r\n"), "--in-place", expect_ok=True)
    art_rows = [e for e in dr.read_directory(three_files) if e.is_art]
    assert art_rows[0].name_exact == b"----------------"
    assert art_rows[1].name_exact == b" DR.J           "


def test_output_file_leaves_the_input_untouched(three_files, art_file, tmp_path, run_tool):
    out = tmp_path / "arted.d64"
    original = three_files.read_bytes()
    run_tool(three_files, "--from-text", art_file(SIMPLE_ART), "-o", out, expect_ok=True)

    assert three_files.read_bytes() == original
    assert [e.is_art for e in dr.read_directory(out)][0] is True


# --------------------------------------------------------------------------
# copying art off another disk
# --------------------------------------------------------------------------

def test_art_can_be_lifted_from_another_d64(three_files, art_file, tmp_path, run_tool):
    source = tmp_path / "source.d64"
    source.write_bytes(three_files.read_bytes())
    run_tool(source, "--from-text", art_file(SIMPLE_ART), "--in-place", expect_ok=True)

    target = three_files
    run_tool(target, "--from-d64", source, "--in-place", expect_ok=True)

    lifted = [e.name_exact for e in dr.read_directory(target) if e.is_art]
    assert b"----------------" in lifted


# --------------------------------------------------------------------------
# refusals
# --------------------------------------------------------------------------

def test_art_line_longer_than_16_chars_is_refused(three_files, art_file, run_tool):
    proc = run_tool(three_files, "--from-text",
                    art_file("this line is far too wide\n"),
                    "--in-place", expect_ok=False)
    assert "directory entry holds 16" in (proc.stdout + proc.stderr)
    assert proc.returncode == 4, "bad art file -> exit 4"


def test_the_offending_line_number_is_reported(three_files, art_file, run_tool):
    """A 40-line art file with one bad row must say which row."""
    art = "----------------\n" * 12 + "this line is far too wide\n"
    proc = run_tool(three_files, "--from-text", art_file(art),
                    "--in-place", expect_ok=False)
    assert "line 13" in (proc.stdout + proc.stderr)


def test_token_naming_no_such_file_is_refused(three_files, art_file, run_tool):
    proc = run_tool(three_files, "--from-text",
                    art_file("@nosuchfile\n"), "--in-place", expect_ok=False)
    assert "match no file" in (proc.stdout + proc.stderr)
    assert "CRACKTRO" in (proc.stdout + proc.stderr), "should list what IS on the disk"
    assert proc.returncode == 5, "unknown token -> exit 5"


def test_both_sources_at_once_is_refused(three_files, art_file, run_tool):
    proc = run_tool(three_files, "--from-text", art_file(SIMPLE_ART),
                    "--from-d64", three_files, "--in-place", expect_ok=False)
    assert "not allowed with" in (proc.stdout + proc.stderr)


def test_neither_source_is_refused(three_files, run_tool):
    proc = run_tool(three_files, "--in-place", expect_ok=False)
    assert "required" in (proc.stdout + proc.stderr)


def test_truncated_image_is_refused(tmp_path, art_file, run_tool):
    stub = tmp_path / "stub.d64"
    stub.write_bytes(b"\x00" * 1024)
    proc = run_tool(stub, "--from-text", art_file(SIMPLE_ART),
                    "--in-place", expect_ok=False)
    assert "not a .d64" in (proc.stdout + proc.stderr)
    assert proc.returncode == 3, "bad image -> exit 3"


# --------------------------------------------------------------------------
# the write destination must be explicit
# --------------------------------------------------------------------------

def test_refuses_to_guess_where_to_write(three_files, art_file, run_tool):
    """Overwriting someone's only copy of a disk must be something they asked for."""
    original = three_files.read_bytes()
    proc = run_tool(three_files, "--from-text", art_file(SIMPLE_ART), expect_ok=False)
    assert "refusing to guess" in (proc.stdout + proc.stderr)
    assert three_files.read_bytes() == original, "must not have touched the disk"


def test_out_and_in_place_together_is_refused(three_files, art_file, tmp_path, run_tool):
    proc = run_tool(three_files, "--from-text", art_file(SIMPLE_ART),
                    "-o", tmp_path / "x.d64", "--in-place", expect_ok=False)
    assert "not allowed with" in (proc.stdout + proc.stderr)


# --------------------------------------------------------------------------
# stamping twice must not accumulate
# --------------------------------------------------------------------------

def test_restamping_replaces_the_art_rather_than_appending(three_files, art_file, run_tool):
    art = art_file(SIMPLE_ART)
    run_tool(three_files, "--from-text", art, "--in-place", expect_ok=True)
    first = three_files.read_bytes()

    run_tool(three_files, "--from-text", art, "--in-place", expect_ok=True)
    second = three_files.read_bytes()

    assert first == second, "stamping the same art twice must be idempotent"
    assert len([e for e in dr.read_directory(three_files) if e.is_art]) == 3


def test_restamping_with_different_art_does_not_keep_the_old(three_files, art_file, run_tool):
    run_tool(three_files, "--from-text", art_file(SIMPLE_ART), "--in-place", expect_ok=True)
    run_tool(three_files, "--from-text",
             art_file("****************\n"), "--out", three_files, expect_ok=True)

    art_rows = [e.name_exact for e in dr.read_directory(three_files) if e.is_art]
    assert art_rows == [b"****************"]


# --------------------------------------------------------------------------
# every bad @token is reported at once
#
# Found by Alex on a real disk: art written for one disk, pointed at another.
# Reporting only the first bad name costs one run per mistake.
# --------------------------------------------------------------------------

def test_all_missing_tokens_are_reported_in_one_run(three_files, art_file, run_tool):
    art = art_file("@nope1\n----------------\n@nope2\n@nope3\n")
    proc = run_tool(three_files, "--from-text", art, "--in-place", expect_ok=False)
    out = proc.stdout + proc.stderr

    for name in ("@NOPE1", "@NOPE2", "@NOPE3"):
        assert name in out, f"{name} missing from the error"
    assert "3 token(s)" in out
    assert proc.returncode == 5


def test_the_error_lists_what_is_actually_on_the_disk(three_files, art_file, run_tool):
    proc = run_tool(three_files, "--from-text", art_file("@nope\n"),
                    "--in-place", expect_ok=False)
    out = proc.stdout + proc.stderr
    for name in ("CRACKTRO", "HRTRAINER", "NOTE"):
        assert name in out, "the fix is knowing which names ARE valid"


def test_a_duplicate_token_is_reported_not_silently_dropped(three_files, art_file, run_tool):
    """Two @cracktro lines, one CRACKTRO on the disk."""
    art = art_file("@cracktro\n----------------\n@cracktro\n")
    proc = run_tool(three_files, "--from-text", art, "--in-place", expect_ok=False)
    out = proc.stdout + proc.stderr
    assert "more times in the art" in out
    assert proc.returncode == 5


def test_a_repeated_name_is_not_confused_with_a_missing_one(three_files, art_file, run_tool):
    """@cracktro twice is a duplicate, not an unknown name."""
    proc = run_tool(three_files, "--from-text",
                    art_file("@cracktro\n@cracktro\n"), "--in-place", expect_ok=False)
    out = proc.stdout + proc.stderr
    assert "match no file" not in out, "CRACKTRO exists; this is a count problem"


def test_a_mix_of_missing_and_duplicated_reports_both(three_files, art_file, run_tool):
    art = art_file("@cracktro\n@cracktro\n@nosuch\n")
    proc = run_tool(three_files, "--from-text", art, "--in-place", expect_ok=False)
    out = proc.stdout + proc.stderr
    assert "@NOSUCH" in out
    assert "more times in the art" in out


def test_the_error_says_tokens_are_disk_specific(three_files, art_file, run_tool):
    """The actual fix is renaming the tokens, so the message should say so."""
    proc = run_tool(three_files, "--from-text", art_file("@nope\n"),
                    "--in-place", expect_ok=False)
    assert "THIS disk" in (proc.stdout + proc.stderr)


def test_progress_output_survives_a_token_failure(three_files, art_file, run_tool):
    """The context lines explain what the tool was doing when it stopped."""
    proc = run_tool(three_files, "--from-text", art_file("@nope\n"),
                    "--in-place", expect_ok=False)
    assert "real file(s) kept" in proc.stdout


def test_a_token_failure_still_writes_nothing(three_files, art_file, run_tool):
    before = three_files.read_bytes()
    run_tool(three_files, "--from-text", art_file("@nope1\n@nope2\n"),
             "--in-place", expect_ok=False)
    assert three_files.read_bytes() == before, "a refusal must not touch the disk"


def test_valid_tokens_still_place_correctly(three_files, art_file, run_tool):
    """The validation pass must not break the happy path."""
    run_tool(three_files, "--from-text",
             art_file("----\n@cracktro\n----\n@note\n"), "--in-place", expect_ok=True)
    entries = dr.read_directory(three_files)
    kinds = [("art" if e.is_art else e.name) for e in entries]
    assert kinds == ["art", "CRACKTRO", "art", "NOTE", "HRTRAINER"]
