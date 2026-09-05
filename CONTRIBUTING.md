# Contributing

<br>

## Running it

```bash
git clone https://github.com/bosai-dj/pyflx4
cd pyflx4
uv sync
uv run pytest
```

**No controller required.** Both MIDI ports are injectable, and the suite drives fakes
that record every message — see `tests/conftest.py`. If running the tests needs hardware
plugged in, that is a bug in this project.

<br>

## Changing a mapping value

This is the part that matters, so it has its own rules.

**A mapping change needs a source, and "my controller does this" is one source, not
two.** The FLX4's deck knobs sit at adjacent CCs (`0x04`, `0x07`, `0x0B`, `0x0F`), which
means a wrong value produces working MIDI aimed at the wrong control — no error, no
crash, just the filter moving when you asked for the bass. Single captures have been
confidently wrong here before.

Cross-check against the [Mixxx FLX4 mapping][mixxx], which carries a plain-English
`<description>` for every control and is exercised by far more hardware than either of us
owns. If your value disagrees with Mixxx, say so explicitly in the PR and explain which
you think is right — that is an interesting finding, not a problem, but it needs to be
argued rather than merged quietly.

**Every value declares its provenance.** `PROVENANCE` in `mapping.py` maps each constant
to `MIXXX`, `CAPTURE`, or `UNVERIFIED`, and a test fails if a constant is missing from
it. Adding a mapping means adding its source in the same commit. Promoting something from
`UNVERIFIED` to `MIXXX` is a genuinely useful contribution on its own.

**Pin it in a test.** `tests/test_mapping.py` asserts the values people get wrong. If your
change touches one of those, the test moves with it and the PR explains why.

<br>

## What a good change looks like

**Tests assert bytes, not calls.** The map is this library's whole value, and the only
way it is wrong is if the emitted MIDI is wrong. `assert out.messages == [[0xB0, 0x0F, 0]]`
says something a mock assertion does not.

**The map stays importable without `python-rtmidi`.** `from pyflx4 import CC` must work
with the bindings absent — people use the map to generate mappings for other software.
The controller classes are imported lazily to make that true, and CI checks it.

**No `print`.** A library writing to stdout is a library you cannot embed. Use the module
logger.

<br>

## Before you open a PR

- `uv run pytest` passes
- New behaviour has a test, including the case it must *not* affect
- A comment explains *why the code is the way it is*, where that is not obvious. Not what
  it does, and not the story of how it was found
- The PR title reads as a release note, because it becomes one verbatim: release notes are
  generated from merged PRs at tag time

Issues and PRs are welcome. There is no response SLA.

<br>

## Releasing

1. Merge everything you want in the release, with PR titles that read as release notes.
   They become the notes verbatim, categorised by label via `.github/release.yml`.
2. Bump `version` in `pyproject.toml` and `__version__` in `src/pyflx4/__init__.py`
   (the release workflow fails if the tag disagrees), via a PR like any other change.
3. Tag it: `git tag v0.1.0 && git push origin v0.1.0`. A tag alone publishes nothing.
4. Create the GitHub Release for that tag with generated notes. **Publishing the Release
   is what triggers the PyPI upload.** A tag is easy to push by accident and impossible
   to retract once it has reached PyPI, so the deliberate act is the gate.

The workflow re-runs the tests, checks the tag against `__version__`, builds, checks the
metadata renders on PyPI, confirms `py.typed` made it into the wheel, publishes via
[Trusted Publishing][tp] (no API token exists in repo secrets), and attaches the artifacts
back to the Release.

**One-time setup:** Trusted Publishing must be configured on PyPI before the first
automated release — add a GitHub publisher for `bosai-dj/pyflx4`, workflow `release.yml`,
environment `pypi`. Until that exists the publish job cannot mint a token.

[mixxx]: https://github.com/mixxxdj/mixxx/blob/main/res/controllers/Pioneer-DDJ-FLX4.midi.xml
[tp]: https://docs.pypi.org/trusted-publishers/
