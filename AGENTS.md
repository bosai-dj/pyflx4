# AGENTS.md

Instructions for coding agents working in this repository.
Human contributors want [CONTRIBUTING.md](CONTRIBUTING.md); this file only covers the
constraints that are invisible from the code and expensive to violate.

## Checks

```bash
uv sync && uv run pytest -q
ruff check .
```

No controller is needed. Both MIDI ports are injectable and the suite drives fakes that
record every message. If a test you write needs hardware attached, it is in the wrong
shape — see `tests/conftest.py`.

## Constraints

**A mapping value needs a source, and one capture is one source.** The deck knobs sit at
adjacent CCs (`0x04`, `0x07`, `0x0B`, `0x0F`), so a value that is off by one control
still emits valid MIDI at the wrong destination. Nothing errors; the filter moves when
the caller asked for the bass. Cross-check against the Mixxx FLX4 mapping, which carries
a plain-English `<description>` per control, before changing anything here.

**Every constant declares its provenance.** `PROVENANCE` in `mapping.py` maps each name
to `MIXXX`, `CAPTURE` or `UNVERIFIED`, and a test fails if a constant is missing from it.
Adding a mapping means adding its source in the same commit. Never quietly promote an
`UNVERIFIED` value to look confirmed.

**Tests assert bytes, not calls.** `assert out.messages == [[0xB0, 0x0F, 0]]` catches a
wrong CC; a mock assertion catches nothing. The map is the whole product, and the only
way it is wrong is if the emitted MIDI is wrong.

**The map must import without `python-rtmidi`.** `from pyflx4 import CC` has to work with
the bindings absent — people read the map to generate mappings for other software, and on
some platforms rtmidi will not build at all. The controller classes are imported lazily
to make that true, and a CI job checks it. Do not add a top-level `import rtmidi`.

**Nothing on the audio path prints.** Use the module logger. A library writing to stdout
cannot be embedded in anything.

**`assert` is not validation.** `python -O` strips it. Argument checks raise `ValueError`.

**The controller sends no note-off.** Release arrives as note-on with velocity 0. Any
decoder branch keyed on `0x8n` is dead code and any handler that waits for note-off
latches forever.

## Writing

Comments explain **why the code is the way it is**, not what it does and not the story of
how the problem was found.

Release notes live on the Releases page and are generated from merged PR titles. There is
no changelog file; do not add one.
