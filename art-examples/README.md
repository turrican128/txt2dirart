# Art examples

Four working art files. Try them on the practice disk, then copy one, edit it,
and point it at your own.

## Start with the practice disk

The download includes **`testdisk.d64`**, a clean disk holding three small
programs: `CRACKTRO`, `HRTRAINER` and `NOTE`. Every example here works on it
as-is:

```
txt2dirart testdisk.d64 --from-text art-examples/02-interleaved.txt --dry-run
txt2dirart testdisk.d64 --from-text art-examples/02-interleaved.txt -o mine.d64
```

Attach `mine.d64` in an emulator, `LOAD"$",8` and `LIST` to see the art, then
`LOAD"HRTRAINER",8` and `RUN` to see that the files still work.

Use `-o` while you experiment. Without it the tool stamps the disk you named,
and the practice disk stops being clean.

## Then your own disk: rename the tokens

`02-interleaved.txt` and `03-petscii-escapes.txt` contain lines like:

```
@cracktro
@hrtrainer
```

A `@token` means "put the real file with this name here", so it only works on a
disk that actually has a file called `CRACKTRO`. The practice disk does. Yours
almost certainly does not, and the tool will stop and tell you every name it
could not find, and what your disk holds instead:

```
!! 2 token(s) match no file on the disk: @CRACKTRO, @HRTRAINER
   the disk contains: TCOM-10
   a token names a file on THIS disk, so art written for another disk needs
   its tokens renamed
```

That is the tool working, not failing. Rename the tokens to your own files and
run it again. Nothing is written when it stops like this.

To see what is on a disk before you start:

```
txt2dirart yourdisk.d64 --from-text art-examples/01-simple-frame.txt --dry-run
```

`01-simple-frame.txt` and `04-blank-rows.txt` have no tokens in them, so they
work on any disk as-is.

## The files

| file | tokens? | what it shows |
|---|---|---|
| `01-simple-frame.txt` | no | the simplest thing that works |
| `02-interleaved.txt` | **yes** | `@tokens` putting real files inside the art |
| `03-petscii-escapes.txt` | **yes** | a rounded PETSCII frame drawn with `\xNN` escapes |
| `04-blank-rows.txt` | no | blank rows as spacing |

## Rules, briefly

- 16 characters per row, maximum. Longer is an error naming the line.
- Lowercase is uppercased. `\xNN` escapes are not.
- A blank line is a full-width blank row; blank lines at the end are dropped.
- `\xNN` counts as one character against the 16, not four.
- Art already on the disk is replaced, not added to.

The full format is in the main [README](../README.md).
