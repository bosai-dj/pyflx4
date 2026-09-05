"""The MIDI map, pinned.

These values were cross-checked against the Pioneer-DDJ-FLX4 mapping shipped by
Mixxx. They are asserted rather than merely documented because an off-by-one map
does not fail loudly — it moves the wrong knob, quietly, forever.
"""

import pytest

from pyflx4 import CC, CH_DECK, CH_MIXER, CH_PADS, NOTE, PAD_NOTE_BASE, Source
from pyflx4.mapping import PROVENANCE, pad_note, provenance, unverified


# The four deck-channel knobs sit at 0x04, 0x07, 0x0B, 0x0F. They are adjacent
# in the same sequence, so a map shifted by one control still looks plausible:
# "trim" would move the highs and "EQ low" would move the filter. Mixxx labels
# them TRIM / EQ HI / EQ MID / EQ LOW respectively.
@pytest.mark.parametrize(
    ("name", "msb", "lsb"),
    [
        ("TRIM", 0x04, 0x24),
        ("EQ_HI", 0x07, 0x27),
        ("EQ_MID", 0x0B, 0x2B),
        ("EQ_LOW", 0x0F, 0x2F),
        ("VOLUME", 0x13, 0x33),
    ],
)
def test_deck_knob_ccs(name, msb, lsb):
    assert CC[name] == msb
    assert CC[f"{name}_LSB"] == lsb


def test_lsb_is_msb_plus_0x20():
    """Every 14-bit control puts its LSB exactly 0x20 above its MSB."""
    for name, msb in CC.items():
        if name.endswith("_LSB"):
            continue
        lsb_name = f"{name}_LSB"
        if lsb_name in CC:
            assert CC[lsb_name] == msb + 0x20, name


def test_deck_two_pads_are_channel_nine():
    """Deck 2's pads are on channel 9. The obvious guess, 8, is wrong."""
    assert CH_PADS == {1: 7, 2: 9}


def test_deck_and_mixer_channels():
    assert CH_DECK == {1: 0, 2: 1}
    assert CH_MIXER == 6


def test_pad_note_bases_per_mode():
    """Pads send a different note range per pad mode, not a mode flag."""
    assert PAD_NOTE_BASE == {
        "hot_cue": 0x00,
        "pad_fx": 0x10,
        "beat_jump": 0x20,
        "sampler": 0x30,
    }


@pytest.mark.parametrize(
    ("mode", "pad", "note"),
    [("hot_cue", 1, 0x00), ("hot_cue", 8, 0x07), ("beat_jump", 1, 0x20), ("sampler", 8, 0x37)],
)
def test_pad_note(mode, pad, note):
    assert pad_note(mode, pad) == note


def test_transport_and_loop_notes():
    assert NOTE["PLAY_PAUSE"] == 0x0B
    assert NOTE["CUE"] == 0x0C
    assert NOTE["SYNC"] == 0x58
    assert NOTE["LOOP_IN"] == 0x10
    assert NOTE["LOOP_OUT"] == 0x11


def test_filter_knobs_are_on_the_mixer_channel():
    """The colour/filter knobs are per-deck but live on channel 6, not the deck
    channel — which is why they are not part of the EQ CC run."""
    assert CC["FILTER_D1"] == 0x17
    assert CC["FILTER_D2"] == 0x18


def test_beat_fx_level_is_cc_two_on_the_fx_channel():
    assert CC["BEAT_FX_LEVEL"] == 0x02


def test_every_mapping_value_declares_provenance():
    """A mapping value with no stated source is a mapping value nobody can trust."""
    missing = [f"NOTE.{k}" for k in NOTE if f"NOTE.{k}" not in PROVENANCE]
    missing += [f"CC.{k}" for k in CC if f"CC.{k}" not in PROVENANCE]
    assert not missing, f"no provenance declared for: {missing}"


def test_provenance_has_no_entries_for_missing_values():
    for key in PROVENANCE:
        table, _, name = key.partition(".")
        assert name in {"NOTE": NOTE, "CC": CC}[table], f"stale provenance entry: {key}"


def test_the_values_people_get_wrong_are_all_cross_checked():
    for name in ("TRIM", "EQ_HI", "EQ_MID", "EQ_LOW", "VOLUME", "CROSSFADER"):
        assert provenance("CC", name) is Source.MIXXX


def test_unverified_set_is_explicit():
    """Kept deliberately small and visible. Growing it should be a decision."""
    assert unverified() == ("CC.HEADPHONES_VOL", "CC.MASTER_VOLUME")
