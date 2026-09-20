# CSDb submission — txt2dirart 1.0

Everything needed to fill in the "Add release" form at
<https://csdb.dk/additem.php?type=release>. Modelled on the png2prg 1.12
entry (<https://csdb.dk/release/?id=252826>), which is the closest
comparable tool release.

**Submit this yourself — under your own CSDb account.**

---

## Form fields

| field | value |
|---|---|
| **Name** | `txt2dirart 1.0` |
| **Type** | `Other Platform C64 Tool` |
| **Released by** | DR.J / Delysid |
| **Release date** | the day you submit |
| **Website** | `https://github.com/turrican128/txt2dirart` |

### Credits

```
Code  -  DR.J of Delysid
```

Add a `Test` line if anyone tries it before you submit. On the png2prg entry
the credits list three outside testers, and a tool release with named testers
reads as vetted rather than thrown over the wall. Worth doing if you can get
one or two people to run it first — it is the single cheapest thing that
raises how the entry is received.

### Downloads

Upload both, in this order:

1. **`txt2dirart-1.0.zip`** — from the GitHub release. Contains
   `txt2dirart.exe`, the Linux binary, the Python source, README, CHANGELOG,
   LICENSE, the art examples, `examples.d64` and `testdisk.d64` (a practice disk the
   examples run against out of the box).
2. **`examples.d64`** — as its own download. On the png2prg entry roughly a
   third of the people who took the tool also took the examples disk, and for
   this tool it is the best possible demo: attach it, `LIST`, and the
   directory *is* the demonstration.

### Screenshot

`docs/listing-on-a-c64.png` — `examples.d64` listed on a real C64 under VICE.
It shows the art, the two PRG files sitting inside it, and the blocks-free
line, which is the whole pitch in one image.

---

## Summary text

CSDb entries for tools are thin — png2prg's has no long write-up, just
metadata, credits, downloads and a link out. Keep it short and let the README
do the work.

```
txt2dirart stamps C64 directory art onto a .d64 from a plain text file.

One line of the text file per directory row. A line of the form @filename
places that real file at that point in the listing, so the art and the files
interleave instead of the art sitting in a block above them. \xNN writes any
PETSCII byte directly, so the graphics characters dir art is built from need
no separate tool.

Command line, no GUI, no dependencies. Single-file binaries for Windows and
Linux; the Python source is one file if you would rather vendor it into a
build script.

Only track 18 is ever written -- every file keeps its start sector and its
length.

Source, full documentation and the art-file format:
https://github.com/turrican128/txt2dirart
```

---

## Before you submit — checklist

- [ ] GitHub release `v1.0` exists and both CI workflows are green
- [ ] Downloaded the zip from the release page and run **both** binaries once
      on a real machine, not just in CI
- [ ] `examples.d64` attaches and `LIST`s correctly on hardware or in VICE
- [ ] `LOAD"DEMO",8` + `RUN` works off that same disk
- [ ] Repository is **public** and the README renders with both screenshots
- [ ] Links in the README are not 404s
