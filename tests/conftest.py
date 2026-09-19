import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = Path(__file__).resolve().parent / "fixtures"
TOOL = ROOT / "txt2dirart.py"

sys.path.insert(0, str(ROOT))


@pytest.fixture
def three_files(tmp_path):
    """A freshly formatted 35-track disk holding CRACKTRO, HRTRAINER and NOTE."""
    dst = tmp_path / "disk.d64"
    shutil.copy(FIXTURES / "three_files.d64", dst)
    return dst


@pytest.fixture
def art_file(tmp_path):
    """Write an art file and hand back its path."""
    def _write(text, name="art.txt"):
        p = tmp_path / name
        # newline="" so we control the line endings the tool has to cope with
        p.write_bytes(text.encode("latin1") if isinstance(text, str) else text)
        return p
    return _write


@pytest.fixture
def run_tool():
    """Invoke the CLI exactly as a user would, returning the CompletedProcess."""
    def _run(*args, expect_ok=None):
        proc = subprocess.run(
            [sys.executable, str(TOOL), *[str(a) for a in args]],
            capture_output=True, text=True,
        )
        if expect_ok is True:
            assert proc.returncode == 0, f"expected success:\n{proc.stdout}\n{proc.stderr}"
        if expect_ok is False:
            assert proc.returncode != 0, f"expected failure but it passed:\n{proc.stdout}"
        return proc
    return _run
