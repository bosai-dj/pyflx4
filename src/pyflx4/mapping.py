"""MIDI map for the Pioneer DDJ-FLX4.

Every constant here carries a provenance entry in :data:`PROVENANCE`, because a
DJ controller map is only as useful as it is trustworthy: a value that is off by
one control does not fail loudly, it silently moves the wrong knob. Three levels:

``MIXXX``
    Cross-checked against the Pioneer-DDJ-FLX4 mapping shipped by Mixxx, which
    is the most widely exercised FLX4 map in existence. These are the values you
    can rely on.
``CAPTURE``
    Read off this hardware with a MIDI monitor, but not present in the Mixxx
    mapping to cross-check against. Correct as far as one unit can tell.
``UNVERIFIED``
    Believed correct, never confirmed. Treat as a starting point, not fact.

Values here have been wrong before, in both directions. The EQ and trim CCs sit
one control apart from each other (0x04, 0x07, 0x0B, 0x0F), which makes an
off-by-one map look plausible and behave subtly wrongly — trim moves the highs,
"low" moves the filter. If you are writing your own map, check against Mixxx
rather than trusting any single capture, this one included.
"""

from enum import Enum


class Source(Enum):
    """How much a mapping value can be trusted. See the module docstring."""

    MIXXX = "cross-checked against the Mixxx DDJ-FLX4 mapping"
    CAPTURE = "captured from live hardware; no external source to cross-check"
    UNVERIFIED = "believed correct, never confirmed"


# ─── Channel map ─────────────────────────────────────────────────────────────

# Channel constants
CH_DECK = {1: 0, 2: 1}          # transport / loop / EQ buttons
CH_PADS = {1: 7, 2: 9}          # hot cue pads  ← FLX4 uses ch 7/9, confirmed from capture
CH_MIXER = 6                     # crossfader, master, headphones

NOTE = {
    # Transport — channel 0 (deck 1) or 1 (deck 2)
    "PLAY_PAUSE":    0x0B,
    "CUE":           0x0C,
    "SYNC":          0x58,
    "SYNC_SHIFTED":  0x60,  # Shift + Sync → cycle tempo range (confirmed from hardware capture)
    # NOTE: Shift is note 0x3F on the deck channel (0/1), NOT 0x63 as an
    # earlier entry here claimed. In practice we don't track shift state —
    # the FLX4 firmware handles it by sending different MIDI notes when
    # shift is held. (0x63 is Beat FX Select on ch 4,
    # defined below.)
    "SHIFT":         0x3F,

    # Loop — confirmed: Loop In = 0x10 on ch 0/1
    "LOOP_IN":       0x10,
    "LOOP_OUT":      0x11,
    "LOOP_ACTIVE":   0x4D,
    "LOOP_HALVE":    0x51,   # ◄ button — confirmed from capture
    "LOOP_DOUBLE":   0x53,   # ► button — confirmed from capture

    # Hot cue pads — 0x00–0x07 on ch 7 (deck 1) / ch 9 (deck 2).
    # Deck 2 is channel 9, NOT 8 — the obvious guess is wrong.
    "HOT_CUE_1":     0x00,
    "HOT_CUE_2":     0x01,
    "HOT_CUE_3":     0x02,
    "HOT_CUE_4":     0x03,
    "HOT_CUE_5":     0x04,
    "HOT_CUE_6":     0x05,
    "HOT_CUE_7":     0x06,
    "HOT_CUE_8":     0x07,

    # Beat FX — master FX section, channel 4 (0x94/0x95).
    # Note: shift is handled by the FLX4 firmware — pressing Shift + a button
    # sends a DIFFERENT MIDI note, not a modifier flag on the same note.
    "BEAT_FX_ON":            0x47,  # FX On/Off → toggle armed Beat FX (echo/reverb)
    "BEAT_FX_ON_SHIFTED":    0x43,  # Shift + FX On/Off → fire armed Release FX
    "BEAT_FX_SELECT":        0x63,  # FX Select → cycle Beat FX forward
    "BEAT_FX_SELECT_SHIFTED":0x64,  # Shift + FX Select → cycle Beat FX backward (confirmed ch4 capture)
    "FX_BEAT_VALUE_LEFT":    0x4A,  # FX ◄ → halve beat_value
    "FX_BEAT_VALUE_RIGHT":   0x4B,  # FX ► → double beat_value
    # (The stale SHIFT: 0x63 entry above collides with this but is never read
    # — firmware doesn't send a discrete shift note on ch 4.)

    # Load buttons — ch 6 (mixer channel), confirmed from capture
    "LOAD_D1":       0x46,   # Load track to Deck 1
    "LOAD_D2":       0x47,   # Load track to Deck 2

    # Pad mode selector buttons — on deck transport ch (0/1)
    # Confirmed from Mixxx DDJ-FLX4 MIDI mapping
    "PAD_HOT_CUE":   0x1B,   # Hot Cue mode
    "PAD_PAD_FX1":   0x1E,   # Pad FX1 mode
    "PAD_BEAT_JUMP":  0x20,   # Beat Jump mode
    "PAD_SAMPLER":   0x22,   # Sampler mode

    # LEDs (write back on same channel as the control)
    "LED_PLAY":      0x0B,
    "LED_CUE":       0x0C,
    "LED_SYNC":      0x58,
    "LED_LOOP_IN":   0x10,
    "LED_LOOP_OUT":  0x11,
    "LED_LOOP_ACTIVE": 0x4D,
}

CC = {
    # Mixer — per-deck, channel 0 (deck 1) or 1 (deck 2)
    # All analog controls are 14-bit hi-res: MSB CC N, LSB CC N+0x20
    "VOLUME":        0x13,   # channel fader MSB  ← was 0x1B, corrected from capture
    "VOLUME_LSB":    0x33,   # channel fader LSB
    "EQ_HI":         0x07,   # EQ hi MSB
    "EQ_HI_LSB":     0x27,   # EQ hi LSB
    "EQ_MID":        0x0B,   # EQ mid MSB
    "EQ_MID_LSB":    0x2B,   # EQ mid LSB
    "EQ_LOW":        0x0F,   # EQ low MSB  ← was 0x0C, corrected from capture
    "EQ_LOW_LSB":    0x2F,   # EQ low LSB
    "TRIM":          0x04,   # trim/gain MSB  ← was 0x00, corrected from capture
    "TRIM_LSB":      0x24,   # trim/gain LSB

    # Tempo slider — 14-bit on deck channel (0/1), NOT CH_MIXER
    # CC 0x00 = MSB (coarse), CC 0x20 = LSB (fine)  ← was 0x0D/0x2D on ch 6
    "TEMPO_MSB":     0x00,   # CC 0
    "TEMPO_LSB":     0x20,   # CC 32

    # Jog wheel — relative CC centered at 64 (>64 forward, <64 backward)
    # CC 0x21 = free spin (no touch)  ← labels were swapped, corrected from capture
    # CC 0x22 = spin with finger touching platter
    # Note 0x36 = jog touch sensor (on=finger down, off=finger up)
    "JOG_SPIN":      0x21,   # free platter spin  ← was 0x22, corrected
    "JOG_SCRATCH":   0x22,   # touch-mode spin
    "JOG_TOUCH":     0x36,   # NOTE (not CC): finger on/off platter

    # Master section — all on CH_MIXER (channel 6), 14-bit
    "CROSSFADER":    0x1F,   # crossfader MSB
    "CROSSFADER_LSB":0x3F,   # crossfader LSB
    "FILTER_D1":     0x17,   # deck 1 color/filter knob MSB ← confirmed from capture
    "FILTER_D1_LSB": 0x37,   # deck 1 color/filter knob LSB
    "FILTER_D2":     0x18,   # deck 2 color/filter knob MSB ← confirmed from capture
    "FILTER_D2_LSB": 0x38,   # deck 2 color/filter knob LSB
    "MASTER_VOLUME": 0x13,   # UNVERIFIED — not in the Mixxx mapping. 0x13 is the
                             # deck channel fader, so this is likely wrong.
    "HEADPHONES_MIX":0x0C,   # confirmed: Mixxx "HEADPHONES MIXING - rotate"
    "HEADPHONES_VOL":0x09,   # UNVERIFIED — not in the Mixxx mapping

    # Browse encoder — relative: 0x01 = CW, 0x7F = CCW — confirmed from capture
    "BROWSE":        0x40,   # CC 0x40 on CH_MIXER (ch 6)

    # Beat FX Level / Depth knob — 14-bit on ch 4 (master FX section).
    # Was 0x1C which didn't match any real hardware control — corrected from
    # live MIDI capture during release-FX wiring.
    "BEAT_FX_LEVEL":     0x02,   # MSB
    "BEAT_FX_LEVEL_LSB": 0x22,   # LSB
}

# ─── State model ─────────────────────────────────────────────────────────────

PAD_MODE_NOTES = {
    NOTE["PAD_HOT_CUE"]:  "hot_cue",
    NOTE["PAD_PAD_FX1"]:  "pad_fx",
    NOTE["PAD_BEAT_JUMP"]: "beat_jump",
    NOTE["PAD_SAMPLER"]:  "sampler",
}
PAD_MODE_TO_NOTE = {v: k for k, v in PAD_MODE_NOTES.items()}

# Pad note bases per mode — pads 1-8 are base + (pad-1)
PAD_NOTE_BASE = {
    "hot_cue":   0x00,
    "pad_fx":    0x10,
    "beat_jump": 0x20,
    "sampler":   0x30,
}
ALL_PAD_BASES = tuple(PAD_NOTE_BASE.values())

def pad_note(mode: str, pad: int) -> int:
    """Return the MIDI note for a pad (1-8) in a given mode."""
    return PAD_NOTE_BASE[mode] + (pad - 1)



# ─── Provenance ──────────────────────────────────────────────────────────────
# Keys are "TABLE.NAME". Every entry in NOTE and CC must appear here; a test
# enforces it, so a new mapping cannot be added without stating where it
# came from.

PROVENANCE: dict[str, Source] = {
    # Transport, loop, pads — all present in the Mixxx mapping.
    **{f"NOTE.{k}": Source.MIXXX for k in (
        "PLAY_PAUSE", "CUE", "SYNC", "LOOP_IN", "LOOP_OUT", "LOOP_ACTIVE",
        "LOOP_HALVE", "LOOP_DOUBLE",
        "HOT_CUE_1", "HOT_CUE_2", "HOT_CUE_3", "HOT_CUE_4",
        "HOT_CUE_5", "HOT_CUE_6", "HOT_CUE_7", "HOT_CUE_8",
        "LOAD_D1", "LOAD_D2",
        "PAD_HOT_CUE", "PAD_PAD_FX1", "PAD_BEAT_JUMP", "PAD_SAMPLER",
        "LED_PLAY", "LED_CUE", "LED_SYNC", "LED_LOOP_IN", "LED_LOOP_OUT",
        "LED_LOOP_ACTIVE",
    )},
    # Shift and the Beat FX section: read off the hardware. The FLX4 firmware
    # sends a *different note* when shift is held rather than a modifier, which
    # is why the shifted variants are separate entries.
    **{f"NOTE.{k}": Source.CAPTURE for k in (
        "SHIFT", "SYNC_SHIFTED",
        "BEAT_FX_ON", "BEAT_FX_ON_SHIFTED",
        "BEAT_FX_SELECT", "BEAT_FX_SELECT_SHIFTED",
        "FX_BEAT_VALUE_LEFT", "FX_BEAT_VALUE_RIGHT",
    )},

    # Mixer and EQ — the values most often gotten wrong, all confirmed.
    **{f"CC.{k}": Source.MIXXX for k in (
        "VOLUME", "VOLUME_LSB",
        "EQ_HI", "EQ_HI_LSB", "EQ_MID", "EQ_MID_LSB", "EQ_LOW", "EQ_LOW_LSB",
        "TRIM", "TRIM_LSB",
        "CROSSFADER", "CROSSFADER_LSB",
        "FILTER_D1", "FILTER_D1_LSB", "FILTER_D2", "FILTER_D2_LSB",
        "BROWSE", "HEADPHONES_MIX",
        "BEAT_FX_LEVEL", "BEAT_FX_LEVEL_LSB",
    )},
    **{f"CC.{k}": Source.CAPTURE for k in (
        "TEMPO_MSB", "TEMPO_LSB", "JOG_SPIN", "JOG_SCRATCH", "JOG_TOUCH",
    )},
    # Not in the Mixxx mapping and not confirmed here. Left in because they are
    # better than nothing, labelled because they are not better than checking.
    **{f"CC.{k}": Source.UNVERIFIED for k in (
        "MASTER_VOLUME", "HEADPHONES_VOL",
    )},
}


def provenance(table: str, name: str) -> Source:
    """Return how far a given mapping value can be trusted.

    >>> provenance("CC", "EQ_LOW")
    <Source.MIXXX: 'cross-checked against the Mixxx DDJ-FLX4 mapping'>
    """
    return PROVENANCE[f"{table}.{name}"]


def unverified() -> tuple[str, ...]:
    """Names of every mapping value that has never been confirmed."""
    return tuple(
        sorted(k for k, v in PROVENANCE.items() if v is Source.UNVERIFIED)
    )
