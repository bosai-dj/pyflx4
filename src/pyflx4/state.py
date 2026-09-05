"""Controller state as this library last observed or set it.

These are a mirror, not a source of truth: the FLX4 does not report its own
positions, so a value here is whatever was last sent or last received. On
connect, the hardware's real fader and knob positions are unknown until the
user physically moves each one.
"""

from dataclasses import dataclass, field


@dataclass
class DeckState:
    deck: int          # 1 or 2
    playing: bool = False
    bpm: float = 128.0
    volume: float = 1.0         # 0.0 – 1.0
    eq_hi: float = 0.0          # -1.0 to +1.0  (maps to 0-127)
    eq_mid: float = 0.0
    eq_low: float = 0.0
    trim: float = 0.5
    loop_active: bool = False
    loop_start_ms: int | None = None
    loop_end_ms: int | None = None
    hot_cues: dict = field(default_factory=dict)  # {1: ms, ...}
    jog_touching: bool = False   # True while finger is on the platter
    pad_mode: str = "hot_cue"    # hot_cue | pad_fx | beat_jump | sampler

@dataclass
class MixerState:
    crossfader: float = 0.5    # 0.0 (full left) – 1.0 (full right)
    master_volume: float = 0.8

