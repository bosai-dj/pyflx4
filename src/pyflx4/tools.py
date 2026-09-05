"""High-level control surface: play, cue, EQ, loops, hot cues, LEDs.

Every method returns a plain dict describing what it did, which makes this layer
straightforward to drive from a CLI, an HTTP handler, or a tool-calling agent
without the library needing to know which.
"""

import threading
import time

from .controller import DDJFLX4
from .mapping import (
    ALL_PAD_BASES,
    CC,
    CH_DECK,
    CH_MIXER,
    CH_PADS,
    NOTE,
    PAD_MODE_TO_NOTE,
    PAD_NOTE_BASE,
)


class DDJFLX4Tools:
    """
    Expose DDJ-FLX4 controls as clean tool functions for an AI agent.
    Each method:
      - Takes human-readable arguments
      - Validates input
      - Sends the correct MIDI message(s)
      - Returns a dict the agent can read as observation
    """

    def __init__(self, controller: DDJFLX4):
        self.ctrl = controller

    def _deck_ch(self, deck: int) -> int:
        """MIDI channel for transport/EQ/loop controls."""
        if deck not in (1, 2):
            raise ValueError(f"deck must be 1 or 2, got {deck!r}")
        return CH_DECK[deck]  # 0 for deck 1, 1 for deck 2

    def _pad_ch(self, deck: int) -> int:
        """MIDI channel for pad (hot cue) controls — ch 7 (deck 1) / ch 9 (deck 2) on FLX4."""
        if deck not in (1, 2):
            raise ValueError(f"deck must be 1 or 2, got {deck!r}")
        return CH_PADS[deck]  # 7 for deck 1, 9 for deck 2

    # ── Transport ─────────────────────────────────────────────────────────────

    def play(self, deck: int) -> dict:
        """Start playback on deck 1 or 2."""
        ch = self._deck_ch(deck)
        self.ctrl.note_on(ch, NOTE["PLAY_PAUSE"])
        time.sleep(0.02)
        self.ctrl.note_off(ch, NOTE["PLAY_PAUSE"])
        self.ctrl.decks[deck].playing = True
        return {"action": "play", "deck": deck, "playing": True}

    def pause(self, deck: int) -> dict:
        """Pause playback on deck 1 or 2."""
        ch = self._deck_ch(deck)
        self.ctrl.note_on(ch, NOTE["PLAY_PAUSE"])
        time.sleep(0.02)
        self.ctrl.note_off(ch, NOTE["PLAY_PAUSE"])
        self.ctrl.decks[deck].playing = False
        return {"action": "pause", "deck": deck, "playing": False}

    def cue(self, deck: int) -> dict:
        """Jump to the cue point on a deck (or set cue if paused)."""
        ch = self._deck_ch(deck)
        self.ctrl.note_on(ch, NOTE["CUE"])
        time.sleep(0.02)
        self.ctrl.note_off(ch, NOTE["CUE"])
        return {"action": "cue", "deck": deck}

    # ── Tempo ─────────────────────────────────────────────────────────────────

    def set_tempo(self, deck: int, bpm: float) -> dict:
        """
        Set the tempo of a deck.
        BPM range: 60.0 – 180.0.
        14-bit pair: CC 0x00 (MSB) + CC 0x20 (LSB) on the deck's transport channel.
        """
        bpm = max(60.0, min(180.0, bpm))
        raw = int(((bpm - 60) / 120) * 16383)
        msb = (raw >> 7) & 0x7F
        lsb = raw & 0x7F
        ch = self._deck_ch(deck)
        self.ctrl.cc(ch, CC["TEMPO_MSB"], msb)
        self.ctrl.cc(ch, CC["TEMPO_LSB"], lsb)
        self.ctrl.decks[deck].bpm = bpm
        return {"action": "set_tempo", "deck": deck, "bpm": bpm}

    def sync_tempo(self, source_deck: int, target_deck: int) -> dict:
        """Sync target deck's BPM to match source deck."""
        source_bpm = self.ctrl.decks[source_deck].bpm
        result = self.set_tempo(target_deck, source_bpm)
        result["synced_from"] = source_deck
        return result

    def jog_nudge(self, deck: int, direction: str, pulses: int = 1) -> dict:
        """
        Nudge the jog wheel to fine-adjust track position or pitch.
        Confirmed encoding from live capture: relative CC centered at 64.
          direction: 'forward' or 'backward'
          pulses: number of incremental steps to send (1 = tiny nudge, 10 = noticeable)
        Uses CC 0x22 (JOG_SPIN) on the deck's transport channel.
        """
        if direction not in ("forward", "backward"):
            raise ValueError(f"direction must be 'forward' or 'backward', got {direction!r}")
        pulses = max(1, min(64, pulses))
        ch = self._deck_ch(deck)
        # >64 = forward, <64 = backward. Use ±1 per pulse for fine control.
        value = 65 if direction == "forward" else 63
        for _ in range(pulses):
            self.ctrl.cc(ch, CC["JOG_SPIN"], value)  # CC 0x21 = free spin
            time.sleep(0.005)
        return {"action": "jog_nudge", "deck": deck, "direction": direction, "pulses": pulses}

    # ── Mixer ─────────────────────────────────────────────────────────────────

    def set_volume(self, deck: int, level: float) -> dict:
        """
        Set the channel fader volume.
        level: 0.0 (silent) to 1.0 (full).
        14-bit hi-res: CC 0x13 (MSB) + CC 0x33 (LSB).
        """
        level = max(0.0, min(1.0, level))
        ch = self._deck_ch(deck)
        raw = int(level * 16383)
        self.ctrl.cc(ch, CC["VOLUME"],     (raw >> 7) & 0x7F)
        self.ctrl.cc(ch, CC["VOLUME_LSB"],  raw & 0x7F)
        self.ctrl.decks[deck].volume = level
        return {"action": "set_volume", "deck": deck, "level": level}

    def set_crossfader(self, position: float) -> dict:
        """
        Move the crossfader.
        0.0 = full deck 1, 0.5 = centre, 1.0 = full deck 2.
        14-bit hi-res: CC 0x1F (MSB) + CC 0x3F (LSB) on CH_MIXER (ch 6).
        """
        position = max(0.0, min(1.0, position))
        raw = int(position * 16383)
        self.ctrl.cc(CH_MIXER, CC["CROSSFADER"],     (raw >> 7) & 0x7F)
        self.ctrl.cc(CH_MIXER, CC["CROSSFADER_LSB"],  raw & 0x7F)
        self.ctrl.mixer.crossfader = position
        return {"action": "set_crossfader", "position": position}

    def set_eq(self, deck: int, hi: float = 0.0, mid: float = 0.0, low: float = 0.0) -> dict:
        """
        Set the 3-band EQ for a deck.
        hi / mid / low: -1.0 (cut) to +1.0 (boost). 0.0 = flat.
        14-bit hi-res pairs on the deck's transport channel.
        """
        ch = self._deck_ch(deck)
        def send14(msb_cc, lsb_cc, v):
            raw = int((v + 1.0) / 2.0 * 16383)
            self.ctrl.cc(ch, msb_cc, (raw >> 7) & 0x7F)
            self.ctrl.cc(ch, lsb_cc,  raw & 0x7F)
        send14(CC["EQ_HI"],  CC["EQ_HI_LSB"],  hi)
        send14(CC["EQ_MID"], CC["EQ_MID_LSB"], mid)
        send14(CC["EQ_LOW"], CC["EQ_LOW_LSB"], low)
        self.ctrl.decks[deck].eq_hi  = hi
        self.ctrl.decks[deck].eq_mid = mid
        self.ctrl.decks[deck].eq_low = low
        return {"action": "set_eq", "deck": deck, "hi": hi, "mid": mid, "low": low}

    def set_trim(self, deck: int, level: float) -> dict:
        """Set the trim/gain for a deck. level: 0.0 to 1.0.
        14-bit hi-res: CC 0x04 (MSB) + CC 0x24 (LSB).
        """
        level = max(0.0, min(1.0, level))
        ch = self._deck_ch(deck)
        raw = int(level * 16383)
        self.ctrl.cc(ch, CC["TRIM"],     (raw >> 7) & 0x7F)
        self.ctrl.cc(ch, CC["TRIM_LSB"],  raw & 0x7F)
        self.ctrl.decks[deck].trim = level
        return {"action": "set_trim", "deck": deck, "level": level}

    # ── Loops ─────────────────────────────────────────────────────────────────

    def set_loop(self, deck: int, active: bool, beats: int | None = None) -> dict:
        """Enable or disable looping on a deck. Optional beats for auto-loop (4, 8, 16)."""
        ch = self._deck_ch(deck)
        if active:
            self.ctrl.note_on(ch, NOTE["LOOP_ACTIVE"])
            time.sleep(0.02)
            self.ctrl.note_off(ch, NOTE["LOOP_ACTIVE"])
        self.ctrl.decks[deck].loop_active = active
        return {"action": "set_loop", "deck": deck, "active": active, "beats": beats}

    def loop_in(self, deck: int) -> dict:
        """Set the loop-in point at the current playhead position."""
        ch = self._deck_ch(deck)
        self.ctrl.note_on(ch, NOTE["LOOP_IN"])
        time.sleep(0.02)
        self.ctrl.note_off(ch, NOTE["LOOP_IN"])
        return {"action": "loop_in", "deck": deck}

    def loop_out(self, deck: int) -> dict:
        """Set the loop-out point and activate the loop."""
        ch = self._deck_ch(deck)
        self.ctrl.note_on(ch, NOTE["LOOP_OUT"])
        time.sleep(0.02)
        self.ctrl.note_off(ch, NOTE["LOOP_OUT"])
        self.ctrl.decks[deck].loop_active = True
        return {"action": "loop_out", "deck": deck}

    # ── Hot cues ──────────────────────────────────────────────────────────────

    def trigger_hot_cue(self, deck: int, pad: int) -> dict:
        """
        Trigger hot cue pad 1-8 on a deck.
        Uses the pad channel: ch 7 for deck 1, ch 9 for deck 2.
        """
        if not 1 <= pad <= 8:
            raise ValueError(f"pad must be 1-8, got {pad!r}")
        ch = self._pad_ch(deck)  # pad channel, NOT the transport channel
        note = NOTE[f"HOT_CUE_{pad}"]
        self.ctrl.note_on(ch, note)
        time.sleep(0.02)
        self.ctrl.note_off(ch, note)
        return {"action": "hot_cue", "deck": deck, "pad": pad}

    def set_pad_led(self, deck: int, pad: int, on: bool,
                    mode: str | None = None, all_modes: bool = False) -> dict:
        """Set LED for a pad (1-8) on the controller.

        Args:
            mode: Send LED on a specific pad mode note base only.
            all_modes: Send LED across ALL pad mode note bases (for stems).
            If neither is set, defaults to the current pad mode.
        """
        ch = CH_PADS[deck]
        vel = 0x7F if on else 0x00
        if all_modes:
            bases = ALL_PAD_BASES
        elif mode:
            bases = (PAD_NOTE_BASE[mode],)
        else:
            current_mode = self.ctrl.decks[deck].pad_mode
            bases = (PAD_NOTE_BASE.get(current_mode, 0x00),)
        for base in bases:
            self.ctrl.note_on(ch, base + (pad - 1), vel)
        return {"action": "set_pad_led", "deck": deck, "pad": pad, "on": on}

    # ── LED feedback ──────────────────────────────────────────────────────────

    def set_led(self, deck: int, control: str, on: bool) -> dict:
        """
        Light up (or turn off) an LED on the controller.
        control: 'play', 'cue', 'sync'
        """
        ch = self._deck_ch(deck)
        note_key = f"LED_{control.upper()}"
        note = NOTE.get(note_key)
        if note is None:
            return {"error": f"Unknown LED control: {control}"}
        velocity = 0x7F if on else 0x00
        self.ctrl.note_on(ch, note, velocity)
        return {"action": "set_led", "deck": deck, "control": control, "on": on}

    def set_pad_mode_led(self, deck: int, mode: str) -> dict:
        """Light the active pad mode button LED and turn off the others.
        mode: 'hot_cue' | 'pad_fx' | 'beat_jump' | 'sampler'
        """
        ch = self._deck_ch(deck)
        active_note = PAD_MODE_TO_NOTE.get(mode)
        for note in PAD_MODE_TO_NOTE.values():
            vel = 0x7F if note == active_note else 0x00
            self.ctrl.note_on(ch, note, vel)
        return {"action": "set_pad_mode_led", "deck": deck, "mode": mode}

    # ── Smooth transitions ────────────────────────────────────────────────────

    def crossfade_over(self, from_deck: int, duration_seconds: float = 4.0) -> dict:
        """
        Gradually move the crossfader from one deck to the other over N seconds.
        Runs in a background thread so the agent doesn't block.
        """
        to_deck = 2 if from_deck == 1 else 1
        start = 0.0 if from_deck == 1 else 1.0
        end   = 1.0 if from_deck == 1 else 0.0
        steps = 50
        delay = duration_seconds / steps

        def _fade():
            for i in range(steps + 1):
                pos = start + (end - start) * (i / steps)
                self.set_crossfader(pos)
                time.sleep(delay)

        threading.Thread(target=_fade, daemon=True).start()
        return {
            "action": "crossfade_over",
            "from_deck": from_deck,
            "to_deck": to_deck,
            "duration_seconds": duration_seconds,
            "note": "running in background"
        }

    # ── State observation ─────────────────────────────────────────────────────

    def get_deck_state(self, deck: int) -> dict:
        """Return the current known state of a deck. Agent uses this as observation."""
        s = self.ctrl.decks[deck]
        return {
            "deck": deck,
            "playing": s.playing,
            "bpm": s.bpm,
            "volume": s.volume,
            "eq": {"hi": s.eq_hi, "mid": s.eq_mid, "low": s.eq_low},
            "trim": s.trim,
            "loop_active": s.loop_active,
            "hot_cues": s.hot_cues,
            "pad_mode": s.pad_mode,
        }

    def get_mixer_state(self) -> dict:
        """Return the current mixer state."""
        return {
            "crossfader": self.ctrl.mixer.crossfader,
            "master_volume": self.ctrl.mixer.master_volume,
        }

    def get_full_state(self) -> dict:
        """Return complete controller state — use as agent context each loop tick."""
        return {
            "deck1": self.get_deck_state(1),
            "deck2": self.get_deck_state(2),
            "mixer": self.get_mixer_state(),
        }

