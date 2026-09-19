# txt2dirart

Stamp C64 **directory art** onto a `.d64` from a plain text file.

No dependencies, no install, no GUI. One file in, one disk out. Windows and Linux binaries need nothing on the machine — not even Python.

```
$ txt2dirart game.d64 --from-text art.txt -o release.d64

    0 "DR.J/DELYSID    " DJ 2A
    0 "================" del
    0 "   DR.J/DELYSID " del
    0 "================" del
    3 "CRACKTRO        " prg
    6 "HRTRAINER       " prg
    1 "NOTE            " prg
```

The listing draws a picture. The files still load.

---

## Contents

- [What directory art is](#what-directory-art-is)
- [Why this exists](#why-this-exists)
- [Install](#install)
- [Quick start](#quick-start)
- [The art file](#the-art-file)
  - [Art rows](#art-rows)
  - [`@tokens` — putting files inside the art](#tokens--putting-files-inside-the-art)
  - [`\xNN` — PETSCII characters you cannot type](#xnn--petscii-characters-you-cannot-type)
- [Command line](#command-line)
- [Exit codes](#exit-codes)
- [Recipes](#recipes)
- [Verifying it worked](#verifying-it-worked)
- [How it works](#how-it-works)
- [Limitations](#limitations)
- [Building from source](#building-from-source)
- [Credits](#credits)

---

## What directory art is

A 1541 directory is a chain of 32-byte entries living on track 18. Each entry has a file type, a start sector, a 16-character name and a block count.

If you write an entry whose type is a **closed DEL** (`$80`) with a block count of **zero**, the drive lists it like any other entry — but it owns no sectors, points at no data, and loading it does nothing. It is a free row of 16 characters in the listing.

Sixteen characters wide, as many rows as track 18 has room for. That is your canvas. That is directory art.

The C64 scene has been doing this since the eighties. This tool just makes it scriptable.

## Why this exists

The existing options all have a catch:

| | catch |
|---|---|
| **DirMaster** | Windows GUI. Excellent, but you cannot call it from a build script. |
| **Sparkle** `DirArt:` | Only if your production is built with Sparkle. |
| **c1541** | No dir-art support at all. |
| **A hex editor** | Works. Once. |

`txt2dirart` is a CLI that stamps art onto a disk that has **already been mastered**. It runs on Windows and Linux, takes a text file you can keep in version control, and — the part nothing else does — can place your real files *inside* the art rather than below it.

## Install

**Binaries** (nothing else needed) — grab the zip from [Releases](https://github.com/turrican128/txt2dirart/releases):

```
txt2dirart.exe          Windows
txt2dirart              Linux x64
```

Drop it anywhere on your `PATH`.

**From source** — any Python 3.8 or newer, no packages required:

```
python txt2dirart.py game.d64 --from-text art.txt -o release.d64
```

The whole tool is one file. You can vendor it into your project and forget about it.

## Quick start

Write an art file:

```
================
   DR.J/DELYSID
================
```

Preview what it will do — this writes nothing:

```
$ txt2dirart game.d64 --from-text art.txt --dry-run
```

Then stamp it:

```
$ txt2dirart game.d64 --from-text art.txt -o release.d64
```

`release.d64` now lists your art above the files. `game.d64` is untouched.

To overwrite the input instead, say so explicitly:

```
$ txt2dirart game.d64 --from-text art.txt --in-place
```

> **The tool will not guess where to write.** You pass `-o` or `--in-place`. Silently overwriting someone's only copy of a disk is the one mistake this tool could make that cannot be undone.

## The art file

One line per directory row, top to bottom. Plain text, any editor, LF or CRLF.

### Art rows

- Up to **16 characters**. Longer is an error naming the line number — it is not silently truncated, because a truncated row is art you did not draw.
- Lowercase is **uppercased**. The C64's default character set has no lowercase; leaving it alone would give you graphics characters instead of letters.
- A **blank line** is a full-width blank row.
- Blank lines at the **end** of the file are dropped. They are almost always trailing newlines rather than deliberate spacing.
- Rows are padded with real spaces (`$20`), not `$A0`. A row padded with `$A0` lists as an *empty name* rather than the full-width row you drew — a classic dir-art bug.

```
----------------

   DR.J PRESENTS

----------------
```

### `@tokens` — putting files inside the art

A line starting with `@` is not art. It means **"put the real file with this name here."**

```
 ..............
 . DR.J/DELYSID
 ..............
@cracktro
 ..............
@hrtrainer
 ..............
    2026
```

gives

```
    0 " .............. " del
    0 " . DR.J/DELYSID " del
    0 " .............. " del
    3 "CRACKTRO        " prg      <- the real file, in the middle of the art
    0 " .............. " del
    6 "HRTRAINER       " prg
    0 " .............. " del
    0 "    2026        " del
    1 "NOTE            " prg      <- not named by a token, so appended
```

Notes:

- Tokens are **case-insensitive**. `@cracktro`, `@CRACKTRO` and `@CrAcKtRo` are the same.
- A token naming a file that is not on the disk is an **error**, and the message lists what *is* on the disk. A silent miss would mean shipping a listing with a hole in it.
- Any real file you do **not** name is appended at the end, and the tool says so. A typo in your art can never drop a file off the disk.
- Use no tokens at all and you get art-then-files (or `--file-first` for files-then-art).

### `\xNN` — PETSCII characters you cannot type

Dir art is built from PETSCII graphics characters — bars, corners, blocks — and your text editor cannot type most of them.

`\xNN` writes PETSCII byte `NN` directly:

```
\xa0\xa0 DR.J/DELYSID
```

- `\xNN` counts as **one character** against the 16-wide limit, not four. Sixteen escapes is a full row.
- Escaped bytes are **not uppercased**. `\x61` stays `$61`; a literal `a` becomes `A`.
- `\\` is a literal backslash.
- A malformed escape is an error with the line number, never a silently mangled row.

> Earlier versions of this code told you to run a separate Windows-only tool afterwards to fix up the graphics characters. That is gone. Everything is done in one pass, on either platform.

To find the code for a character you want, any PETSCII chart will do — the codes here are the ones the drive sends and the C64 prints, i.e. PETSCII, not screen codes.

## Command line

```
txt2dirart DISK.D64 (--from-text ART.TXT | --from-d64 ART.D64)
           [-o OUT.D64 | --in-place] [--file-first] [--dry-run] [-q]
```

| option | meaning |
|---|---|
| `--from-text ART.TXT` | art file, one line per row |
| `--from-d64 ART.D64` | lift the art off another disk's listing |
| `-o, --out OUT.D64` | write the result here |
| `--in-place` | overwrite the input image |
| `--file-first` | files above the art (default: art above the files) |
| `--dry-run` | print the listing it *would* write, then stop |
| `-q, --quiet` | only report problems |
| `--version` | print the version |

`--from-d64` is how you borrow: point it at any disk whose listing you like and its rows become your art.

## Exit codes

Refusals are typed, so a build script can tell them apart:

| code | meaning |
|---:|---|
| `0` | done |
| `2` | bad command line (argparse) |
| `3` | the image is not a `.d64` we can work with |
| `4` | the art file does not parse |
| `5` | an `@token` names no file on the disk |
| `6` | track 18 is full |

## Recipes

**In a build script**, after mastering the disk:

```sh
c1541 -format "my game,dj" d64 out/game.d64 \
      -write build/cracktro.prg cracktro \
      -write build/game.prg game
txt2dirart out/game.d64 --from-text dirart.txt --in-place || exit 1
```

**Steal a listing you like:**

```sh
txt2dirart mine.d64 --from-d64 theirs.d64 -o mine-arted.d64
```

**Check the art still fits after adding a file:**

```sh
txt2dirart out/game.d64 --from-text dirart.txt --dry-run
```

## Verifying it worked

Three levels, cheapest first.

**1. `--dry-run`.** Shows the listing, including the real disk name, ID and DOS type from the BAM.

**2. `c1541`:**

```sh
c1541 out/game.d64 -list
```

**3. A real drive or an emulator.** Attach the disk and:

```
LOAD"$",8
LIST
```

This is the only check that shows you the actual PETSCII glyphs. Do it once before you release anything — a `\xNN` chosen from the wrong chart looks perfectly fine in `--dry-run` and wrong on a C64.

**And load a file.** The whole point is that the art is free:

```
LOAD"CRACKTRO",8,1
```

## How it works

Only **track 18** is ever written. Everything else in the image — every file's data, the other tracks, any error-info block — is returned byte for byte as it came in. The test suite asserts exactly this.

1. Walk the directory chain from track 18 sector 1, collecting every in-use entry.
2. Split them into real files and existing art (DEL entries owning no block), so re-stamping replaces the art instead of piling it up.
3. Build the new entry list: art rows, with real files slotted in at their `@tokens`.
4. Grow the chain along track 18 if the entries need more sectors, taking the BAM's free sectors at the usual interleave of 3 and marking them allocated.
5. Rewrite every sector in the chain, fixing the link bytes — including the two that overlap entry 0's first two bytes.
6. Write to a temp file and `os.replace` it into position, so an interrupted run cannot leave a half-written disk image.

## Limitations

- **35- and 40-track `.d64` only** (`174848`, `175531`, `196608`, `197376` bytes). No `.d71`, no `.d81`, no `.g64`.
- **Track 18 is the ceiling.** 18 usable sectors × 8 entries = **144 rows** absolute maximum, shared with your real files, and only if the rest of track 18 is free. You will hit a clean error long before you hit anything weird.
- **It does not draw the art for you.** It takes the art you wrote and puts it on the disk. Authoring is DirMaster, a text editor, or your own head.
- **It does not write files.** Master the disk first with `c1541` or whatever you already use, then stamp it.

## Building from source

```sh
git clone https://github.com/turrican128/txt2dirart
cd txt2dirart
python -m pytest tests/ -q
```

The tests need only Python. The fixture disks are committed as binaries so nothing has to be installed; `python tools/make_fixtures.py --check` rebuilds them with `c1541` and proves the committed copies match.

Release binaries are built by GitHub Actions with PyInstaller on `windows-latest` and `ubuntu-latest`.

## Credits

Code by **DR.J/Delysid**.

Written while cracking *The Human Race* (Mastertronic, 1985) — the crack needed a dir-art step that ran on Linux from a build script, and nothing did that.

MIT licensed. Do what you like with it.
