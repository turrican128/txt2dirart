# Changelog

## 1.0

First public release.

### What it does

- Stamps directory art onto a `.d64` from a plain text file (`--from-text`), or
  by lifting the listing off another disk (`--from-d64`).
- `@token` placement: a line like `@cracktro` puts that real file at that point
  in the listing, so files can sit *inside* the art instead of below it. Any
  file not named by a token is appended at the end, so a typo in the art can
  never drop a file off the disk.
- `\xNN` escapes write PETSCII bytes directly, so the graphics characters dir
  art is built from -- frames, corners, lines -- need no separate tool. An
  escape counts as one character against the 16-wide limit and is not
  uppercased the way plain text is.
- 35- and 40-track images, with and without error info.
- The plain command stamps the disk you named; `-o OUT.D64` writes a new disk
  and leaves the original alone. Only track 18 is ever rewritten: every file
  keeps its start sector and its length.
- Directory art already on the disk is replaced, not added to, so stamping is
  repeatable: edit the text file, stamp again, and the disk matches the file.
- `--dry-run` prints the listing it would write -- disk name, ID and DOS type
  included -- and touches nothing.
- `--file-first`, `--quiet`, `--version`.

### When something is wrong, it says so

- Every bad `@token` is reported in one run, together with the names of the
  files that *are* on the disk. Tokens name files, so art written for one disk
  needs its tokens renamed for another.
- Naming a file more times than the disk has copies of it is an error, not a
  silently missing row.
- Art errors (a row over 16 characters, a malformed escape) name the line.
- Warns when the image does not look like a formatted 1541 disk, and when it
  holds no files at all. Warnings, not refusals: art-only disks are a real use.
- Typed exit codes: 3 bad image, 4 bad art file, 5 bad token, 6 track 18 full.
- Atomic writes: an interrupted run cannot leave a half-written disk image.

### In the download

- Single-file binaries for Windows and Linux x64. Nothing to install, not even
  Python.
- `txt2dirart.py`, the whole tool in one dependency-free file (Python 3.9+), if
  you would rather vendor it into a build script.
- `art-examples/` with four working art files and notes on adapting them.
- `testdisk.d64`, a clean practice disk holding the files the examples place,
  so every example runs out of the box.
- `examples.d64`: attach it and `LIST` -- the directory is the demonstration,
  and `LOAD"DEMO",8` then `RUN` shows the files still load.
