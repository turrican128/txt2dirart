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
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KIT = ROOT.parent / "txt2dirart-TESTKIT"

# Disk images this repo owns, as {name in the kit: source in the repo}.
# Anything else in the kit is the user's and is never touched.
#
# testdisk.d64 is reset to pristine on every refresh, on purpose: the plain
# command stamps in place, so after a test pass it is covered in art, and the
# guide's examples assume the three files and nothing else.
OURS = {
    "examples.d64": "examples.d64",
    "testdisk.d64": "testdisk.d64",          # the practice disk that ships in the zip
}

EXCLUDES = [
    "tkinter", "unittest", "email", "http", "xml", "xmlrpc", "pydoc",
    "doctest", "pdb", "sqlite3", "ssl", "hashlib", "lzma", "bz2", "socket",
    "multiprocessing", "asyncio", "logging", "pickle", "json", "csv",
    "decimal", "datetime", "calendar",
]


def sh(*args, **kw):
    return subprocess.run(args, capture_output=True, text=True, **kw)


MANIFEST = ".kit-manifest.json"


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_manifest():
    try:
        return json.loads((KIT / MANIFEST).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def copy_example(src, dst, manifest, kept):
    """Copy one shipped example into the kit without eating Alex's edits.

    He edits the examples while testing. The manifest records the hash of
    what this script last wrote; if the file in the kit no longer matches
    it, he changed it, and his version is set aside as NAME.yours.EXT
    before the new one lands. With no manifest entry (first run), any file
    that differs from the incoming copy is treated as his, to be safe.
    """
    rel = "art-examples/" + dst.name
    if dst.exists():
        current = digest(dst)
        last_written = manifest.get(rel)
        edited = (current != last_written) if last_written else (current != digest(src))
        if edited and current != digest(src):
            backup = dst.with_name(dst.stem + ".yours" + dst.suffix)
            if backup.exists():
                backup = dst.with_name(dst.stem + time.strftime(".yours-%H%M%S") + dst.suffix)
            shutil.copy(dst, backup)
            kept.append(f"{dst.name} -> {backup.name}")
    shutil.copy(src, dst)
    manifest[rel] = digest(dst)


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


def write_build_info(exe, branch, sha, subject):
    (KIT / "BUILD-INFO.txt").write_text(f"""txt2dirart test build
=====================

Built : {time.strftime('%Y-%m-%d %H:%M')}
From  : {branch} @ {sha}
Size  : {exe.stat().st_size} bytes

Latest change:
  {subject}

Confirm you are running THIS build:

    txt2dirart.exe --version
    dir txt2dirart.exe        -> {exe.stat().st_size} bytes

Refreshed by tools/refresh_testkit.py.

Two disks here belong to the kit and are RESET on every refresh:
    examples.d64   the demo disk that ships with the release
    testdisk.d64   CRACKTRO, HRTRAINER, NOTE -- the guide's examples use it

Every other .d64 in this folder is yours and is never touched.
""", encoding="utf-8")


def main():
    if not KIT.exists():
        sys.exit(f"!! test kit not found at {KIT}")

    exe = build()
    smoke(exe)

    shutil.copy(exe, KIT / exe.name)
    (KIT / "art-examples").mkdir(exist_ok=True)
    manifest, kept = load_manifest(), []
    for f in sorted((ROOT / "art-examples").iterdir()):
        if f.is_file():
            copy_example(f, KIT / "art-examples" / f.name, manifest, kept)
    (KIT / MANIFEST).write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    for name, source in OURS.items():
        if (ROOT / source).exists():
            shutil.copy(ROOT / source, KIT / name)

    branch = sh("git", "-C", str(ROOT), "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
    sha = sh("git", "-C", str(ROOT), "rev-parse", "--short", "HEAD").stdout.strip()
    subject = sh("git", "-C", str(ROOT), "log", "-1", "--pretty=%s").stdout.strip()
    write_build_info(exe, branch, sha, subject)

    shutil.rmtree(ROOT / "build", ignore_errors=True)
    shutil.rmtree(ROOT / "dist", ignore_errors=True)
    (ROOT / "txt2dirart.spec").unlink(missing_ok=True)

    print(f"[*] test kit refreshed: {KIT}")
    print(f"    {exe.name}  {(KIT / exe.name).stat().st_size} bytes  ({branch} @ {sha})")
    for line in kept:
        print("    your edit kept: " + line)
    theirs = sorted(p.name for p in KIT.glob("*.d64") if p.name not in OURS)
    if theirs:
        print("    left alone: " + ", ".join(theirs))
    return 0


if __name__ == "__main__":
    sys.exit(main())
