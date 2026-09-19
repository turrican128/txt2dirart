"""The BASIC builder behind examples.d64.

It caught a real bug the first time it was checked: the last line's link
pointer was zero, which makes BASIC stop *before* that line, so the final
line silently never ran. These tests decode the program back and walk the
link chain, which is the only way that class of bug shows up.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import make_examples as mk  # noqa: E402

LINES = [(10, '?"ONE"'), (20, '?"TWO"'), (30, '?"THREE"')]


def decode(prg):
    """Walk the program the way the interpreter does, returning its lines."""
    load = int.from_bytes(prg[:2], "little")
    out = []
    pos = 2
    while True:
        link = int.from_bytes(prg[pos:pos + 2], "little")
        if link == 0:
            break
        number = int.from_bytes(prg[pos + 2:pos + 4], "little")
        i = pos + 4
        while prg[i] != 0:
            i += 1
        body = prg[pos + 4:i]
        # where the next line actually begins, in C64 address terms
        actual = load + (i + 1 - 2)
        out.append((number, body, link, actual))
        pos = i + 1
    return out


def test_every_line_survives_the_link_walk():
    """The bug that started this file: the last line vanished."""
    decoded = decode(mk.build_basic(LINES))
    assert [n for n, *_ in decoded] == [10, 20, 30]


def test_every_link_points_at_the_next_line():
    for number, _body, link, actual in decode(mk.build_basic(LINES)):
        assert link == actual, f"line {number}: link ${link:04X} != ${actual:04X}"


def test_program_ends_with_the_null_terminator():
    prg = mk.build_basic(LINES)
    assert prg[-2:] == b"\x00\x00"


def test_last_link_points_at_the_terminator_not_zero():
    prg = mk.build_basic(LINES)
    load = int.from_bytes(prg[:2], "little")
    *_, (_, _, last_link, _) = decode(prg)
    terminator_addr = load + len(prg) - 2 - 2
    assert last_link == terminator_addr
    assert last_link != 0


def test_print_is_tokenized():
    body = decode(mk.build_basic([(10, '?"HI"')]))[0][1]
    assert body[0] == 0x99, "? must tokenise to PRINT ($99)"


def test_question_mark_inside_a_string_is_literal():
    body = decode(mk.build_basic([(10, '?"WHY?"')]))[0][1]
    assert body.count(b"\x99") == 1, "only the leading ? is a token"
    assert body.endswith(b'WHY?"')


def test_clear_screen_escape():
    body = decode(mk.build_basic([(10, '?"{}HI"')]))[0][1]
    assert b"\x93" in body


def test_the_shipped_demo_program_is_complete():
    """Every line in BASIC_LINES must be reachable, not just the first few."""
    decoded = decode(mk.build_basic(mk.BASIC_LINES))
    assert [n for n, *_ in decoded] == [n for n, _ in mk.BASIC_LINES]
