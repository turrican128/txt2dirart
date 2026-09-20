# Art examples

Four working art files. Copy one, edit it, point it at your disk.

## Read this before you run them

**The `@tokens` in these files name files on MY test disk, not yours.**

`02-interleaved.txt` and `03-petscii-escapes.txt` contain lines like:

```
@cracktro
@hrtrainer
```

A `@token` means "put the real file with this name here", so it only works on a
disk that actually has a file called `CRACKTRO`. Point one of these at your own
disk and the tool will stop and tell you which names it could not find, and what
your disk holds instead:

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

The full format is in the main [README](../README.md).
