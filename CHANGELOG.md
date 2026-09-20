# Changelog

## 1.0.0

First public release.

### Features

- Stamp directory art onto a `.d64` from a plain text file (`--from-text`) or
  by lifting the listing off another disk (`--from-d64`).
- `@token` placement: put real files *inside* the art instead of below it.
  Any file not named by a token is appended, so a typo cannot drop a file.
- `\xNN` escapes write PETSCII bytes directly, so the graphics characters dir
  art is built from need no external tool. Escapes count as one character
  against the 16-wide limit and are not uppercased.
- 35- and 40-track images, with and without error info.
- `--dry-run` prints the listing it would write, disk name and ID included.
- `--file-first`, `--quiet`, `--version`.
- Typed exit codes (3 bad image, 4 bad art, 5 unknown token, 6 track 18 full).
- Atomic writes: an interrupted run cannot leave a half-written disk image.

### Notes for anyone who used the pre-release script

- The tool no longer overwrites its input by default. Pass `-o OUT.D64` or
  `--in-place`.
- `d64nice.exe` is no longer needed for art using the long-line PETSCII
  characters; use `\xNN` instead.

## Unreleased

- Every bad `@token` is now reported in one run, with the disk's actual file
  names and a note that tokens are disk-specific. Previously only the first
  bad name was shown, so fixing an art file written for a different disk cost
  one run per mistake. Found by Alex testing against a real disk.
- Naming a file more times than the disk has copies of it is now an error
  instead of one placement silently vanishing.
- Errors no longer jump ahead of the progress output when stdout is piped.
- Release binaries exclude the stdlib modules the tool never imports: the
  Windows build drops from 8.0 MB to 5.1 MB. (They are not stripped --
  `--strip` produces a Windows binary that cannot start.)
- Tags with a suffix (`v0.9.0-rc1`) publish as prereleases.
- Warns when the image does not look like a formatted 1541 disk (no `2A` DOS
  type, wrong DOS version, BAM not pointing at t18/s1) and when it holds no
  files at all. Warnings, not refusals: art-only disks are a real use. Found
  by Alex pointing the tool at a blank image and reading "0 real file(s) kept"
  as the tool having done nothing.
- **The plain command stamps the disk you named.** An earlier pre-release
  demanded `-o` or `--in-place` and refused otherwise. Only track 18 is ever
  rewritten, so in-place is a safe default, and the refusal also hid the
  disk-sanity warnings: it fired before the image was even opened.
  `--in-place` is still accepted, so scripts written against the old contract
  keep working.
- `art-examples/03-petscii-escapes.txt` now draws a rounded PETSCII frame
  instead of rows of invisible shifted-space, and the README documents the six
  frame codes, verified on a real C64. Alex's idea, after building one for his
  own disk.
- The Linux binary is stripped (the Windows one is not): most of its 12 MB was
  libpython carrying its debug symbols.
- The release zip now includes `art-examples/README.md` and the screenshots the
  README embeds, and the build fails if any expected file is missing from it.
