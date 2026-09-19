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
- Release binaries are stripped and exclude unused stdlib modules: the Windows
  build drops from 8.0 MB to 5.0 MB.
- Tags with a suffix (`v0.9.0-rc1`) publish as prereleases.
