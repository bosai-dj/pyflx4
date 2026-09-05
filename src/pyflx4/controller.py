"""Raw MIDI transport for the DDJ-FLX4: connect, send, listen.

This layer knows about MIDI messages and nothing about DJing. For play/pause,
EQ and crossfader calls, see :mod:`pyflx4.tools`.
"""

import logging
import time

from .mapping import CC, CH_MIXER, NOTE, PAD_MODE_NOTES, PAD_NOTE_BASE
from .state import DeckState, MixerState

logger = logging.getLogger(__name__)


class DDJFLX4:
    """
    Low-level MIDI interface to the DDJ-FLX4.
    Instantiate once, then use the high-level tool methods below.
    """

    DEVICE_NAME = "DDJ-FLX4"

    def __init__(self, on_action=None, debug=False, midi_out=None, midi_in=None):
        """Connect to the controller.

        ``midi_out`` / ``midi_in`` accept anything implementing the small slice
        of the rtmidi port API this uses — ``get_ports``, ``open_port``,
        ``send_message``, and ``set_callback`` on the input. Passing fakes lets
        the whole control surface be exercised without hardware attached, which
        is how this library's own tests assert the exact bytes each call emits.
        Left as None, real rtmidi ports are opened.

        Raises:
            RuntimeError: if no DDJ-FLX4 output port is found.
        """
        if midi_out is None or midi_in is None:
            import rtmidi  # imported here so the MIDI map is usable without it

            midi_out = rtmidi.MidiOut() if midi_out is None else midi_out
            midi_in = rtmidi.MidiIn() if midi_in is None else midi_in
        self.midi_out   = midi_out
        self.midi_in    = midi_in
        self._connect()
        self.decks      = {1: DeckState(1), 2: DeckState(2)}
        self.mixer      = MixerState()
        self._tempo_msb = {}   # {deck: last MSB byte}
        self._cc_msb    = {}   # {(channel, cc_msb): last MSB byte} for 14-bit assembly
        self.on_action  = on_action
        self.debug      = debug
        self.midi_log   = []   # last 30 raw events
        self._start_listener()

    # Pioneer DJ SysEx init — tells the controller that software is connected.
    # Without this, the FLX4 stays in a half-init state with flashing Loop In/Out LEDs.
    # Sequence: MIDI Identity Request + Pioneer vendor "software takeover" message.
    _SYSEX_INIT: tuple[tuple[int, ...], ...] = (
        (0xF0, 0x7E, 0x7F, 0x06, 0x01, 0xF7),              # Identity Request (Universal)
        (0xF0, 0x00, 0x40, 0x05, 0x00, 0x00, 0x00,          # Pioneer vendor header
         0x17, 0x00, 0x50, 0x01, 0xF7),                      # FLX4 software takeover
    )

    def _connect(self):
        out_ports = self.midi_out.get_ports()
        in_ports  = self.midi_in.get_ports()
        for i, name in enumerate(out_ports):
            if self.DEVICE_NAME in name:
                self.midi_out.open_port(i)
                logger.info("MIDI out connected: %s", name)
                break
        else:
            raise RuntimeError(
                f"DDJ-FLX4 not found. Available: {out_ports}"
            )
        for i, name in enumerate(in_ports):
            if self.DEVICE_NAME in name:
                self.midi_in.open_port(i)
                logger.info("MIDI in connected: %s", name)
                break
        # Send SysEx init to put controller in software mode
        for sysex_msg in self._SYSEX_INIT:
            self.midi_out.send_message(sysex_msg)
            time.sleep(0.05)
        logger.info("SysEx init sent; controller should now be in software mode")

    def _send(self, status: int, data1: int, data2: int):
        self.midi_out.send_message([status, data1, data2])

    def note_on(self, channel: int, note: int, velocity: int = 0x7F):
        self._send(0x90 | channel, note, velocity)

    def note_off(self, channel: int, note: int):
        self._send(0x80 | channel, note, 0x00)

    def cc(self, channel: int, control: int, value: int):
        """Send a Control Change. Value 0-127."""
        self._send(0xB0 | channel, control, value)

    def _start_listener(self):
        """Background thread: update internal state from controller input."""
        self.midi_in.set_callback(self._on_midi_in)
        self.midi_in.ignore_types(sysex=True, timing=True, active_sense=True)

    def _on_midi_in(self, event, data=None):
        msg, _ = event
        if not msg:
            return
        status, d1, d2 = msg[0], msg[1], msg[2] if len(msg) > 2 else 0
        ch = status & 0x0F
        kind = status & 0xF0

        if self.debug:
            entry = {"status": hex(status), "ch": ch, "kind": hex(kind), "d1": hex(d1), "d2": d2}
            self.midi_log.append(entry)
            if len(self.midi_log) > 100:
                self.midi_log.pop(0)

        # Transport/loop buttons: ch 0 = deck 1, ch 1 = deck 2
        deck_from_transport = {0: 1, 1: 2}.get(ch)
        # Pad channels come in shifted/unshifted pairs, both belonging to the same
        # deck: 7 = deck 1, 8 = deck 1 + shift, 9 = deck 2, 10 = deck 2 + shift.
        # Reading channel 8 as deck 2 — an easy assumption, since 7 and 9 are the
        # two unshifted ones — reports every shifted deck-1 pad as a deck-2 press.
        deck_from_pads = {7: 1, 8: 1, 9: 2, 10: 2}.get(ch)

        def fire(action, deck, value):
            if self.on_action:
                try:
                    self.on_action(action, deck, value)
                except Exception:
                    # Never let a caller's callback kill the MIDI listener thread,
                    # but never swallow it either — this is their bug to see.
                    logger.exception("on_action callback raised for %r", action)

        if deck_from_transport and kind == 0xB0:
            deck = deck_from_transport

            # ── 14-bit assembly: MSB cached, LSB triggers fire ────────
            # All analog controls on the FLX4 send MSB then LSB.
            # We only fire on LSB with the full 14-bit value to avoid
            # double-firing and coarse intermediate glitches.

            def _cache_msb():
                self._cc_msb[(ch, d1)] = d2

            def _hi14(msb_cc):
                msb = self._cc_msb.get((ch, msb_cc), 0)
                return ((msb << 7) | d2) / 16383.0

            # Volume (MSB 0x13, LSB 0x33)
            if d1 == CC["VOLUME"]:
                _cache_msb()
            elif d1 == CC["VOLUME_LSB"]:
                val = _hi14(CC["VOLUME"])
                self.decks[deck].volume = val
                fire("volume", deck, val)

            # EQ Hi (MSB 0x07, LSB 0x27)
            elif d1 == CC["EQ_HI"]:
                _cache_msb()
            elif d1 == CC["EQ_HI_LSB"]:
                val = _hi14(CC["EQ_HI"]) * 2.0 - 1.0
                self.decks[deck].eq_hi = val
                fire("eq_hi", deck, val)

            # EQ Mid (MSB 0x0B, LSB 0x2B)
            elif d1 == CC["EQ_MID"]:
                _cache_msb()
            elif d1 == CC["EQ_MID_LSB"]:
                val = _hi14(CC["EQ_MID"]) * 2.0 - 1.0
                self.decks[deck].eq_mid = val
                fire("eq_mid", deck, val)

            # EQ Low (MSB 0x0F, LSB 0x2F)
            elif d1 == CC["EQ_LOW"]:
                _cache_msb()
            elif d1 == CC["EQ_LOW_LSB"]:
                val = _hi14(CC["EQ_LOW"]) * 2.0 - 1.0
                self.decks[deck].eq_low = val
                fire("eq_low", deck, val)

            # Trim (MSB 0x04, LSB 0x24)
            elif d1 == CC["TRIM"]:
                _cache_msb()
            elif d1 == CC["TRIM_LSB"]:
                val = _hi14(CC["TRIM"])
                self.decks[deck].trim = val
                fire("trim", deck, val)

            # Tempo (MSB 0x00, LSB 0x20)
            elif d1 == CC["TEMPO_MSB"]:
                _cache_msb()
            elif d1 == CC["TEMPO_LSB"]:
                val = _hi14(CC["TEMPO_MSB"])
                self.decks[deck].bpm = 60.0 + val * 120.0
                fire("tempo", deck, val * 2.0)

            elif d1 == CC["JOG_SPIN"]:       # rim — always pitch bend
                fire("jog_spin", deck, d2 - 64)
            elif d1 == CC["JOG_SCRATCH"]:    # platter top — scratch/seek
                fire("jog_scratch", deck, d2 - 64)
        elif ch == CH_MIXER and kind == 0xB0:

            def _cache_msb_m():
                self._cc_msb[(ch, d1)] = d2

            def _hi14_m(msb_cc):
                msb = self._cc_msb.get((ch, msb_cc), 0)
                return ((msb << 7) | d2) / 16383.0

            # Crossfader (MSB 0x1F, LSB 0x3F)
            if d1 == CC["CROSSFADER"]:
                _cache_msb_m()
            elif d1 == CC["CROSSFADER_LSB"]:
                val = _hi14_m(CC["CROSSFADER"])
                self.mixer.crossfader = val
                fire("crossfader", 0, val)

            # Filter D1 (MSB 0x17, LSB 0x37)
            elif d1 == CC["FILTER_D1"]:
                _cache_msb_m()
            elif d1 == CC["FILTER_D1_LSB"]:
                fire("filter", 1, _hi14_m(CC["FILTER_D1"]))

            # Filter D2 (MSB 0x18, LSB 0x38)
            elif d1 == CC["FILTER_D2"]:
                _cache_msb_m()
            elif d1 == CC["FILTER_D2_LSB"]:
                fire("filter", 2, _hi14_m(CC["FILTER_D2"]))

            elif d1 == CC["BROWSE"]:
                # Relative encoder: 0x01 = CW (forward), 0x7F = CCW (backward)
                direction = 1 if d2 == 1 else -1
                fire("browse", 0, direction)
        elif ch == CH_MIXER and kind == 0x90:
            # Load buttons on ch 6 — note on only
            if d1 == NOTE["LOAD_D1"] and d2 > 0:
                fire("load_deck", 1, 0)
            elif d1 == NOTE["LOAD_D2"] and d2 > 0:
                fire("load_deck", 2, 0)
        elif ch == 4 and kind == 0xB0:
            # Master FX section CCs (ch 4). Currently just the 14-bit Level/Depth knob.
            def _cache_msb_fx():
                self._cc_msb[(ch, d1)] = d2

            def _hi14_fx(msb_cc):
                msb = self._cc_msb.get((ch, msb_cc), 0)
                return ((msb << 7) | d2) / 16383.0

            if d1 == CC["BEAT_FX_LEVEL"]:
                _cache_msb_fx()
            elif d1 == CC["BEAT_FX_LEVEL_LSB"]:
                fire("fx_depth", 0, _hi14_fx(CC["BEAT_FX_LEVEL"]))
        elif ch == 4 and kind == 0x90:
            # Master FX section (ch 4).
            # BEAT_FX_ON (no shift): toggle continuous Beat FX (echo/reverb).
            # BEAT_FX_ON_SHIFTED (shift held): gate Release FX — press fires,
            # release cancels and restores normal playback.
            if d1 == NOTE["BEAT_FX_SELECT"] and d2 > 0:
                fire("release_fx_cycle", 0, 0)
            elif d1 == NOTE["BEAT_FX_SELECT_SHIFTED"] and d2 > 0:
                fire("release_fx_cycle_prev", 0, 0)
            elif d1 == NOTE["BEAT_FX_ON"] and d2 > 0:
                fire("beat_fx_toggle", 0, 0)
            elif d1 == NOTE["BEAT_FX_ON_SHIFTED"]:
                if d2 > 0:
                    fire("release_fx_fire", 0, 0)
                else:
                    fire("release_fx_end", 0, 0)
            elif d1 == NOTE["FX_BEAT_VALUE_LEFT"] and d2 > 0:
                fire("fx_beat_halve", 0, 0)
            elif d1 == NOTE["FX_BEAT_VALUE_RIGHT"] and d2 > 0:
                fire("fx_beat_double", 0, 0)
        elif deck_from_transport and kind == 0x90:
            deck = deck_from_transport
            if d1 == NOTE["PLAY_PAUSE"] and d2 > 0:
                self.decks[deck].playing = not self.decks[deck].playing
                fire("play_pause", deck, self.decks[deck].playing)
            elif d1 == NOTE["CUE"] and d2 > 0:
                fire("cue", deck, 0)
            elif d1 == NOTE["SYNC"] and d2 > 0:
                fire("sync", deck, 0)
            elif d1 == NOTE["SYNC_SHIFTED"] and d2 > 0:
                fire("tempo_range_cycle", deck, 0)
            elif d1 == NOTE["LOOP_IN"] and d2 > 0:
                fire("loop_in", deck, 0)
            elif d1 == NOTE["LOOP_OUT"] and d2 > 0:
                fire("loop_out", deck, 0)
            elif d1 == NOTE["LOOP_ACTIVE"] and d2 > 0:
                self.decks[deck].loop_active = not self.decks[deck].loop_active
                fire("loop_toggle", deck, self.decks[deck].loop_active)
            elif d1 == NOTE["LOOP_HALVE"] and d2 > 0:
                fire("loop_halve", deck, 0)
            elif d1 == NOTE["LOOP_DOUBLE"] and d2 > 0:
                fire("loop_double", deck, 0)
            elif d1 in PAD_MODE_NOTES and d2 > 0:
                mode = PAD_MODE_NOTES[d1]
                self.decks[deck].pad_mode = mode
                fire("pad_mode", deck, mode)
            elif d1 == CC["JOG_TOUCH"]:
                touching = (d2 > 0)
                self.decks[deck].jog_touching = touching
                fire("jog_touch", deck, 1 if touching else 0)
        elif deck_from_pads and kind == 0x90 and d2 > 0:
            deck = deck_from_pads
            # Each pad mode sends on a different note base (all on ch 7 / ch 9).
            # Use PAD_NOTE_BASE to map note ranges to mode-specific actions.
            matched = False
            for mode_name, base in PAD_NOTE_BASE.items():
                if base <= d1 <= base + 7:
                    fire(f"pad_{mode_name}", deck, d1 - base + 1)
                    matched = True
                    break
            if not matched and self.debug:
                logger.debug("unhandled pad note: ch=%d note=0x%02X vel=%d", ch, d1, d2)

    def close(self):
        self.midi_out.close_port()
        self.midi_in.close_port()


# ─── High-level tool functions (agent calls these) ────────────────────────────
