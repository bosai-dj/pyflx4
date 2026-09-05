"""Decoding what the controller sends us.

Input is where the map earns its keep in the other direction: a 14-bit control
arrives as two separate CC messages, and reassembling them against the wrong
CC number silently attributes a knob turn to the wrong control.
"""

import pytest


def feed(controller, status, d1, d2=0):
    """Deliver one MIDI message the way rtmidi's callback would."""
    controller._on_midi_in(([status, d1, d2], 0.0))


def actions(controller):
    seen = []
    controller.on_action = lambda *a: seen.append(a)
    return seen


def test_play_button_updates_deck_state(controller):
    feed(controller, 0x90, 0x0B, 0x7F)
    assert controller.decks[1].playing is True


def test_jog_touch_note_tracks_finger_on_platter(controller):
    """The FLX4 signals release as note-on with velocity 0, never as note-off.

    Its entire MIDI vocabulary is 0x9n; there is not a single 0x8n message in
    the Mixxx mapping. Decoders that listen only for note-off therefore latch a
    held button forever, which is why the release below is velocity 0.
    """
    feed(controller, 0x90, 0x36, 0x7F)
    assert controller.decks[1].jog_touching is True
    feed(controller, 0x90, 0x36, 0x00)
    assert controller.decks[1].jog_touching is False


def test_14bit_volume_reassembles_from_msb_and_lsb(controller):
    """MSB alone must not be taken as the value; the pair is one control."""
    feed(controller, 0xB0, 0x13, 127)   # MSB
    feed(controller, 0xB0, 0x33, 127)   # LSB
    assert controller.decks[1].volume == pytest.approx(1.0, abs=1e-3)


def test_14bit_volume_at_zero(controller):
    feed(controller, 0xB0, 0x13, 0)
    feed(controller, 0xB0, 0x33, 0)
    assert controller.decks[1].volume == pytest.approx(0.0, abs=1e-3)


def test_eq_low_cc_moves_eq_low_not_the_filter(controller):
    """The inbound half of the off-by-one trap."""
    feed(controller, 0xB0, 0x0F, 0)
    feed(controller, 0xB0, 0x2F, 0)
    assert controller.decks[1].eq_low == pytest.approx(-1.0, abs=1e-2)


def test_deck_two_eq_arrives_on_channel_one(controller):
    feed(controller, 0xB1, 0x0F, 0)
    feed(controller, 0xB1, 0x2F, 0)
    assert controller.decks[2].eq_low == pytest.approx(-1.0, abs=1e-2)
    assert controller.decks[1].eq_low == pytest.approx(0.0)


def test_pad_press_reports_mode_and_pad_number(controller):
    seen = actions(controller)
    feed(controller, 0x97, 0x20, 0x7F)   # deck 1 pads, beat-jump base
    assert ("pad_beat_jump", 1, 1) in seen


def test_deck_two_pads_arrive_on_channel_nine(controller):
    seen = actions(controller)
    feed(controller, 0x99, 0x00, 0x7F)   # deck 2 pads, hot-cue base
    assert ("pad_hot_cue", 2, 1) in seen


def test_empty_message_is_ignored(controller):
    controller._on_midi_in(([], 0.0))    # must not raise


def test_running_status_two_byte_message_is_tolerated(controller):
    controller._on_midi_in(([0x90, 0x0B], 0.0))


def test_shifted_deck_one_pads_are_not_deck_two(controller):
    """Channel 8 is deck 1 with shift held, not deck 2.

    7 and 9 are the two unshifted pad channels, which makes 8 look like it ought
    to be deck 2. It is not: the pairs are 7/8 for deck 1 and 9/10 for deck 2.
    """
    seen = actions(controller)
    feed(controller, 0x98, 0x00, 0x7F)
    assert ("pad_hot_cue", 1, 1) in seen
    assert not any(a[1] == 2 for a in seen)
