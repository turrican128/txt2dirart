"""testdisk.d64 -- the practice disk that ships in the release zip.

Alex asked why it was not in the zip. It had never been decided either way,
and its absence was a real hole: examples 02 and 03 place files with
@cracktro and @hrtrainer, and the only disk in the download held DEMO and
README. The two most interesting examples failed on first contact.

These tests are about the shipped pair: the shipped examples must work
against the shipped disk, out of the box, with no renaming.
"""
import shutil
import sys
from pathlib import Path

import d64reader as dr
import pytest

ROOT = Path(__file__).resolve().parent.parent
PRACTICE = ROOT / "testdisk.d64"
EXAMPLES = sorted((ROOT / "art-examples").glob("*.txt"))

sys.path.insert(0, str(ROOT / "tools"))
import make_examples as mk  # noqa: E402


@pytest.fixture
def practice(tmp_path):
    dst = tmp_path / "testdisk.d64"
    shutil.copy(PRACTICE, dst)
    return dst


def test_the_practice_disk_is_committed():
    assert PRACTICE.exists(), "testdisk.d64 must ship -- the examples depend on it"
    assert PRACTICE.stat().st_size == 174848


def test_it_holds_exactly_the_files_the_examples_name():
    got = [(e.name, e.blocks) for e in dr.read_directory(PRACTICE)]
    assert got == [("CRACKTRO", 3), ("HRTRAINER", 6), ("NOTE", 1)], \
        "the README's sample output shows these three at these sizes"


def test_it_ships_pristine_with_no_art_on_it():
    """The plain command stamps in place, so one careless run of an example
    against the repo's copy would commit a disk covered in art."""
    assert not any(e.is_art for e in dr.read_directory(PRACTICE))


@pytest.mark.parametrize("art", EXAMPLES, ids=lambda p: p.name)
def test_every_shipped_example_works_on_the_shipped_disk(art, practice, run_tool):
    """Out of the box: no token renaming, no other disk needed."""
    run_tool(practice, "--from-text", art, expect_ok=True)
    assert sorted(e.name for e in dr.real_files(practice)) == \
        ["CRACKTRO", "HRTRAINER", "NOTE"]


def test_stamping_leaves_the_practice_files_byte_identical(practice, run_tool):
    before = practice.read_bytes()
    run_tool(practice, "--from-text", ROOT / "art-examples" / "02-interleaved.txt",
             expect_ok=True)
    after = practice.read_bytes()
    for track in list(range(1, 18)) + list(range(19, 36)):
        for sector in range(dr.sectors_in_track(track)):
            off = dr.byte_offset(track, sector)
            assert before[off:off + 256] == after[off:off + 256]


# --------------------------------------------------------------------------
# the files are real programs, not junk bytes -- someone will LOAD and RUN them
# --------------------------------------------------------------------------

def walk(prg):
    """Follow the BASIC link chain the way the interpreter does."""
    load = int.from_bytes(prg[:2], "little")
    lines, pos = [], 2
    while True:
        link = int.from_bytes(prg[pos:pos + 2], "little")
        if link == 0:
            return lines
        number = int.from_bytes(prg[pos + 2:pos + 4], "little")
        end = prg.index(0, pos + 4)
        assert link == load + (end + 1 - 2), f"line {number}: bad link pointer"
        lines.append((number, prg[pos + 4:end]))
        pos = end + 1


@pytest.mark.parametrize("name,blocks", mk.PRACTICE_FILES)
def test_practice_programs_are_valid_basic(name, blocks):
    prg = mk.practice_prg(name, blocks)
    lines = walk(prg)
    assert lines, "no lines"
    assert lines[0][1][0] == 0x99, "first line must PRINT"
    assert name.upper().encode() in lines[0][1], "the file announces itself"
    assert prg[-2:] == b"\x00\x00"


@pytest.mark.parametrize("name,blocks", mk.PRACTICE_FILES)
def test_practice_programs_fill_exactly_their_block_count(name, blocks):
    assert mk.blocks_of(mk.practice_prg(name, blocks)) == blocks


def test_padding_lines_are_rem_and_never_execute():
    """Six blocks of padding must not turn RUN into a wall of output."""
    lines = walk(mk.practice_prg("hrtrainer", 6))
    padding = [body for number, body in lines if number >= 1000]
    assert padding, "a six-block file needs padding"
    assert all(body[0] == 0x8F for body in padding), "padding must be REM"
    printing = [body for _, body in lines if body[0] == 0x99]
    assert len(printing) == 4, "RUN prints four lines, however big the file is"


# --------------------------------------------------------------------------
# art-examples/README.md makes claims about the files next to it
#
# It said 04-blank-rows.txt had no tokens and "works on any disk as-is" while
# the file contained @cracktro. Nothing checked, so it stayed wrong from the
# day it was written until the day before release.
# --------------------------------------------------------------------------

def readme_token_claims():
    claims = {}
    for line in (ROOT / "art-examples" / "README.md").read_text(encoding="utf-8").splitlines():
        cells = [c.strip() for c in line.split("|")]
        if len(cells) >= 4 and cells[1].startswith("`0") and cells[1].endswith(".txt`"):
            claims[cells[1].strip("`")] = "yes" in cells[2].lower()
    return claims


def test_the_readme_table_lists_every_shipped_example():
    assert sorted(readme_token_claims()) == sorted(p.name for p in EXAMPLES)


@pytest.mark.parametrize("art", EXAMPLES, ids=lambda p: p.name)
def test_the_readme_is_right_about_which_examples_have_tokens(art):
    has_tokens = any(l.startswith(b"@") for l in art.read_bytes().splitlines())
    assert readme_token_claims()[art.name] == has_tokens, \
        f"README says tokens={readme_token_claims()[art.name]} for {art.name}, file says {has_tokens}"


@pytest.mark.parametrize("art", EXAMPLES, ids=lambda p: p.name)
def test_token_free_examples_really_work_on_any_disk(art, tmp_path, run_tool):
    """'Works on any disk as-is' is a promise. Hold it to a disk with one
    unrelated file on it."""
    if readme_token_claims()[art.name]:
        pytest.skip("has tokens; disk-specific by design")
    other = tmp_path / "other.d64"
    shutil.copy(ROOT / "examples.d64", other)      # holds DEMO and README only
    run_tool(other, "--from-text", art, expect_ok=True)
