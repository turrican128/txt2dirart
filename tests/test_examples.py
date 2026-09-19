"""Every art file shipped in art-examples/ must actually work.

The README points people at these. If one stops parsing -- a 17th character
creeps in, an escape goes stale -- the first person to find out should be a
test, not someone reading the README.
"""
from pathlib import Path

import d64reader as dr
import pytest

EXAMPLES = sorted((Path(__file__).resolve().parent.parent / "art-examples").glob("*.txt"))


def test_there_are_examples_to_check():
    assert EXAMPLES, "art-examples/ is empty -- the README references it"


@pytest.mark.parametrize("art", EXAMPLES, ids=lambda p: p.name)
def test_example_stamps_cleanly(art, three_files, tmp_path, run_tool):
    out = tmp_path / "out.d64"
    run_tool(three_files, "--from-text", art, "-o", out, expect_ok=True)

    entries = dr.read_directory(out)
    assert any(e.is_art for e in entries), f"{art.name} produced no art rows"
    assert sorted(e.name for e in dr.real_files(out)) == \
        ["CRACKTRO", "HRTRAINER", "NOTE"], f"{art.name} lost a file"


@pytest.mark.parametrize("art", EXAMPLES, ids=lambda p: p.name)
def test_example_rows_are_all_sixteen_bytes(art, three_files, tmp_path, run_tool):
    out = tmp_path / "out.d64"
    run_tool(three_files, "--from-text", art, "-o", out, expect_ok=True)
    for e in dr.read_directory(out):
        assert len(e.name_exact) == 16
