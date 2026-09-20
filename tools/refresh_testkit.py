#!/usr/bin/env python3
"""Rebuild the binary and refresh Alex's test kit from the current checkout.

Run this after EVERY bug fix. A stale binary in the test kit means he
re-finds bugs that are already fixed, which is exactly what happened once
already -- he spent a session testing a build from before two fixes landed.

    python tools/refresh_testkit.py

What it touches:  txt2dirart.exe, art-examples/, examples.d64, BUILD-INFO.txt
What it never touches: any .d64 in the kit that this repo did not put there.
His own test disks live in that folder and are his.
"""
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KIT = ROOT.parent / "txt2dirart-TESTKIT"

# Disk images this repo owns. Anything else in the kit is the user's.
OURS = {"examples.d64"}

EXCLUDES = [
    "tkinter", "unittest", "email", "http", "xml", "xmlrpc", "pydoc",
    "doctest", "pdb", "sqlite3", "ssl", "hashlib", "lzma", "bz2", "socket",
    "multiprocessing", "asyncio", "logging", "pickle", "json", "csv",
    "decimal", "datetime", "calendar",
]


def sh(*args, **kw):
    return subprocess.run(args, capture_output=True, text=True, **kw)


def build():
    """Build with the same flags the release workflow uses. No --strip:
    it corrupts the bundled python DLL on Windows (v0.9.0-rc2 died on it)."""
    for junk in ("build", "dist"):
        shutil.rmtree(ROOT / junk, ignore_errors=True)
    (ROOT / "txt2dirart.spec").unlink(missing_ok=True)

    cmd = [sys.executable, "-m", "PyInstaller", "--onefile",
           "--name", "txt2dirart", "--console", "--noupx"]
    for mod in EXCLUDES:
        cmd += ["--exclude-module", mod]
    cmd.append(str(ROOT / "txt2dirart.py"))

    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    if r.returncode:
        sys.exit("!! build failed:\n" + r.stdout[-2000:] + r.stderr[-2000:])

    exe = ROOT / "dist" / ("txt2dirart.exe" if os.name == "nt" else "txt2dirart")
    if not exe.exists():
        sys.exit(f"!! no binary at {exe}")
    return exe


def smoke(exe):
    """A binary that builds is not a binary that runs. Exercise it."""
    disk = ROOT / "tests" / "fixtures" / "three_files.d64"
    tmp = ROOT / "dist" / "smoke.d64"
    shutil.copy(disk, tmp)
    bad = ROOT / "dist" / "bad.txt"
    bad.write_text("@nosuchfile\n")

    checks = [
        ([str(exe), "--version"], 0),
        ([str(exe), str(disk), "--from-text",
          str(ROOT / "art-examples" / "01-simple-frame.txt"), "--dry-run"], 0),
        ([str(exe), str(tmp), "--from-text",
          str(ROOT / "art-examples" / "02-interleaved.txt"), "--in-place"], 0),
        ([str(exe), str(tmp), "--from-text", str(bad), "--in-place"], 5),
        # the plain form, no destination flag: stamps the named disk
        ([str(exe), str(tmp), "--from-text",
          str(ROOT / "art-examples" / "01-simple-frame.txt")], 0),
    ]
    for cmd, want in checks:
        got = subprocess.run(cmd, capture_output=True, text=True).returncode
        if got != want:
            sys.exit(f"!! smoke test failed: expected exit {want}, got {got}\n"
                     f"   {' '.join(cmd)}")
    print("[*] binary smoke test passed")


def write_build_info(exe, sha, subject):
    (KIT / "BUILD-INFO.txt").write_text(f"""txt2dirart test build
=====================

Built : {time.strftime('%Y-%m-%d %H:%M')}
From  : main @ {sha}
Size  : {exe.stat().st_size} bytes

Latest change on main:
  {subject}

Confirm you are running THIS build:

    txt2dirart.exe --version
    dir txt2dirart.exe        -> {exe.stat().st_size} bytes

Refreshed by tools/refresh_testkit.py. Your own .d64 files in this
folder are never touched by it.
""", encoding="utf-8")


def main():
    if not KIT.exists():
        sys.exit(f"!! test kit not found at {KIT}")

    exe = build()
    smoke(exe)

    shutil.copy(exe, KIT / exe.name)
    (KIT / "art-examples").mkdir(exist_ok=True)
    for f in (ROOT / "art-examples").iterdir():
        if f.is_file():
            shutil.copy(f, KIT / "art-examples" / f.name)
    for name in OURS:
        if (ROOT / name).exists():
            shutil.copy(ROOT / name, KIT / name)

    sha = sh("git", "-C", str(ROOT), "rev-parse", "--short", "HEAD").stdout.strip()
    subject = sh("git", "-C", str(ROOT), "log", "-1", "--pretty=%s").stdout.strip()
    write_build_info(exe, sha, subject)

    shutil.rmtree(ROOT / "build", ignore_errors=True)
    shutil.rmtree(ROOT / "dist", ignore_errors=True)
    (ROOT / "txt2dirart.spec").unlink(missing_ok=True)

    print(f"[*] test kit refreshed: {KIT}")
    print(f"    {exe.name}  {(KIT / exe.name).stat().st_size} bytes  (main @ {sha})")
    theirs = sorted(p.name for p in KIT.glob("*.d64") if p.name not in OURS)
    if theirs:
        print("    left alone: " + ", ".join(theirs))
    return 0


if __name__ == "__main__":
    sys.exit(main())
