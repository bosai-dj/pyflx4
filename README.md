# pyflx4

[![tests](https://github.com/bosai-dj/pyflx4/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/bosai-dj/pyflx4/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/pyflx4?cacheSeconds=300)](https://pypi.org/project/pyflx4/)
[![Python versions](https://img.shields.io/pypi/pyversions/pyflx4?cacheSeconds=300)](https://pypi.org/project/pyflx4/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

Python control for the Pioneer DDJ-FLX4, with a MIDI map that states where every
value came from.

```bash
pip install pyflx4
```

```python
from pyflx4 import DDJFLX4, DDJFLX4Tools

dj = DDJFLX4Tools(DDJFLX4())

dj.play(deck=1)
dj.set_eq(deck=1, low=-1.0)        # kill the bass on deck 1
dj.set_crossfader(0.5)
dj.trigger_hot_cue(deck=2, pad=1)
```

## Why the map is the point

The FLX4's four deck knobs sit at CC `0x04`, `0x07`, `0x0B`, `0x0F` — adjacent
values in one run. A map shifted by a single position still looks entirely
plausible and still *works*, in the sense that turning things produces MIDI. It
just moves the wrong control: trim adjusts the highs, "EQ low" sweeps the filter.
Nothing errors. You find out by ear, mid-set.

Every value in `pyflx4.mapping` was cross-checked against the
[Pioneer-DDJ-FLX4 mapping shipped by Mixxx][mixxx], the most widely exercised
FLX4 map in existence, and the ones that matter are asserted in the test suite
rather than merely documented.

Where a value could not be cross-checked, the library says so:

```python
>>> from pyflx4 import provenance, unverified
>>> provenance("CC", "EQ_LOW")
<Source.MIXXX: 'cross-checked against the Mixxx DDJ-FLX4 mapping'>
>>> unverified()
('CC.HEADPHONES_VOL', 'CC.MASTER_VOLUME')
```

Two values are unverified, and they are named. That is the whole list.

## The things that cost people an afternoon

- **Deck 2's pads are on channel 9, not 8.** Deck 1 is 7. The obvious guess is wrong.
- **Pads send a different note range per mode**, not a mode flag: hot cue `0x00`,
  pad FX `0x10`, beat jump `0x20`, sampler `0x30`. Listening only at `0x00` means
  your hot cues stop working the moment the user switches pad mode.
- **The controller never sends note-off.** Release is note-on with velocity 0 —
  there is not one `0x8n` message in its vocabulary. Decoders waiting for note-off
  latch a held button forever.
- **Every analog control is a 14-bit pair**, LSB exactly `0x20` above MSB. Reading
  the MSB alone gives you a control that works but jumps in 128 steps.
- **Shift is not a modifier.** The firmware sends a *different note* when shift is
  held, so there is no shift state to track.
- **The tempo fader is on the deck channel**, not the mixer channel where the rest
  of the faders live.

## Two layers

`DDJFLX4` is raw MIDI: connect, send notes and CCs, receive input, drive LEDs.
`DDJFLX4Tools` sits on top and speaks in DJ terms — `play`, `set_eq`, `set_loop`,
`trigger_hot_cue` — returning a plain dict from each call, so it drops into a CLI,
an HTTP handler, or a tool-calling agent without the library caring which.

Both MIDI ports are injectable, so the whole control surface can be driven with
no hardware attached:

```python
controller = DDJFLX4(midi_out=fake_out, midi_in=fake_in)
```

That is how this library's own tests assert the exact bytes each call emits.

## Reading the map without the hardware bindings

`from pyflx4 import CC, NOTE` works without `python-rtmidi` installed — the
controller classes are imported lazily. The map is useful on its own, for
generating a mapping for other software or for checking your own values against
these.

## Related

[flx4py][flx4py] is another Python FLX4 library, and covers LED animation and an
event system more thoroughly than this one does. Check its EQ and trim CCs
against your hardware before relying on them; at the time of writing they sit one
control away from the values in the Mixxx mapping.

[Mixxx][mixxx] itself is the reference if you want the complete picture,
including every shifted note. It is GPL-2.0 and written as a JavaScript mapping,
so it is a source to read rather than one to depend on from Python.

## Status

`0.1.0`. 40 tests, no hardware required to run them. Extracted from a working
system, so the paths exercised in anger — transport, EQ, crossfader, loops, hot
cues, pad modes — are the solid ones. The API is not settled; feedback before
`1.0` is welcome.

See [CONTRIBUTING.md](CONTRIBUTING.md) to build on it and [SECURITY.md](SECURITY.md)
to report a vulnerability.

## License

MIT

[mixxx]: https://github.com/mixxxdj/mixxx/blob/main/res/controllers/Pioneer-DDJ-FLX4.midi.xml
[flx4py]: https://github.com/TRC-Loop/flx4py
