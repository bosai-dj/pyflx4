"""What each call actually puts on the wire.

Asserting bytes rather than mocking calls: the map is this library's whole
value, and the only way it is wrong is if the emitted MIDI is wrong.
"""

import pytest


def test_play_pulses_note_on_then_off_on_the_deck_channel(dj, ports):
    out, _ = ports
    dj.play(deck=1)
    assert out.messages == [[0x90, 0x0B, 0x7F], [0x80, 0x0B, 0x00]]


def test_deck_two_transport_uses_channel_one(dj, ports):
    out, _ = ports
    dj.play(deck=2)
    assert [m[0] for m in out.messages] == [0x91, 0x81]


def test_set_eq_emits_three_14bit_pairs_in_hi_mid_low_order(dj, ports):
    out, _ = ports
    dj.set_eq(deck=1, hi=0.0, mid=0.0, low=0.0)
    # flat == mid-scale == 8191 -> MSB 63, LSB 127
    assert out.messages == [
        [0xB0, 0x07, 63], [0xB0, 0x27, 127],
        [0xB0, 0x0B, 63], [0xB0, 0x2B, 127],
        [0xB0, 0x0F, 63], [0xB0, 0x2F, 127],
    ]


def test_killing_the_low_targets_cc_0x0f_not_the_filter(dj, ports):
    """The regression this library exists to prevent: 0x0F is EQ LOW. A map
    shifted by one would send the filter knob here instead."""
    out, _ = ports
    dj.set_eq(deck=1, low=-1.0)
    assert [0xB0, 0x0F, 0] in out.messages
    assert [0xB0, 0x2F, 0] in out.messages


def test_volume_is_14bit_on_0x13(dj, ports):
    out, _ = ports
    dj.set_volume(deck=1, level=1.0)
    assert out.messages == [[0xB0, 0x13, 127], [0xB0, 0x33, 127]]


def test_volume_clamps_out_of_range(dj, ports):
    out, _ = ports
    dj.set_volume(deck=1, level=5.0)
    assert out.messages == [[0xB0, 0x13, 127], [0xB0, 0x33, 127]]
    out.sent.clear()
    dj.set_volume(deck=1, level=-2.0)
    assert out.messages == [[0xB0, 0x13, 0], [0xB0, 0x33, 0]]


def test_crossfader_is_on_the_mixer_channel(dj, ports):
    out, _ = ports
    dj.set_crossfader(1.0)
    assert out.messages == [[0xB6, 0x1F, 127], [0xB6, 0x3F, 127]]


def test_hot_cue_uses_the_pad_channel_not_the_deck_channel(dj, ports):
    out, _ = ports
    dj.trigger_hot_cue(deck=2, pad=1)
    # deck 2 pads are channel 9 -> status 0x99
    assert out.messages[0][0] == 0x99
    assert out.messages[0][1] == 0x00


def test_state_mirrors_what_was_sent(dj):
    dj.set_volume(deck=1, level=0.25)
    dj.set_eq(deck=1, low=-1.0)
    st = dj.get_deck_state(1)
    assert st["volume"] == pytest.approx(0.25)
    assert st["eq"]["low"] == pytest.approx(-1.0)


def test_full_state_covers_both_decks_and_mixer(dj):
    st = dj.get_full_state()
    assert set(st) == {"deck1", "deck2", "mixer"}
