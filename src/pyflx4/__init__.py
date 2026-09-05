"""Python control for the Pioneer DDJ-FLX4 DJ controller.

    from pyflx4 import DDJFLX4, DDJFLX4Tools

    controller = DDJFLX4()
    dj = DDJFLX4Tools(controller)
    dj.play(deck=1)
    dj.set_eq(deck=1, low=-1.0)

Two layers. :class:`DDJFLX4` is raw MIDI — connect, send notes and CCs, receive
input, drive LEDs. :class:`DDJFLX4Tools` sits on top and speaks in DJ terms.

The MIDI map lives in :mod:`pyflx4.mapping`, where every value records where it
came from. See that module before trusting any of it.
"""

from .mapping import (
    CC,
    CH_DECK,
    CH_MIXER,
    CH_PADS,
    NOTE,
    PAD_MODE_NOTES,
    PAD_NOTE_BASE,
    PROVENANCE,
    Source,
    pad_note,
    provenance,
    unverified,
)
from .state import DeckState, MixerState

# DDJFLX4 and DDJFLX4Tools are imported on first access rather than here, so that
# `from pyflx4 import CC` works without python-rtmidi present. The map is useful
# on its own — for generating mappings for other software, or for checking a
# value against this one — and that should not require the hardware bindings.
_LAZY = {"DDJFLX4": ".controller", "DDJFLX4Tools": ".tools"}


def __getattr__(name: str):
    if name in _LAZY:
        from importlib import import_module

        return getattr(import_module(_LAZY[name], __name__), name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(__all__)

__version__ = "0.1.0"

__all__ = [
    "CC",
    "CH_DECK",
    "CH_MIXER",
    "CH_PADS",
    "DDJFLX4",
    "NOTE",
    "PAD_MODE_NOTES",
    "PAD_NOTE_BASE",
    "PROVENANCE",
    "DDJFLX4Tools",
    "DeckState",
    "MixerState",
    "Source",
    "__version__",
    "pad_note",
    "provenance",
    "unverified",
]
