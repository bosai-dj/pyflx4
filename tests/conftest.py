"""A fake rtmidi port pair, so the whole control surface is testable offline."""

import pytest

DEVICE = "DDJ-FLX4 MIDI 1"


class FakeOut:
    """Records every message instead of sending it."""

    def __init__(self, ports=(DEVICE,)):
        self._ports = list(ports)
        self.opened = None
        self.sent: list[list[int]] = []

    def get_ports(self):
        return list(self._ports)

    def open_port(self, index):
        self.opened = index

    def send_message(self, message):
        self.sent.append(list(message))

    def close_port(self):
        self.opened = None

    # Messages with the SysEx init filtered out — tests care about control
    # traffic, and the init burst is the same two messages every time.
    @property
    def messages(self):
        return [m for m in self.sent if m and m[0] != 0xF0]

    def only(self):
        assert len(self.messages) == 1, f"expected 1 message, got {self.messages}"
        return self.messages[0]


class FakeIn(FakeOut):
    def __init__(self, ports=(DEVICE,)):
        super().__init__(ports)
        self.callback = None

    def set_callback(self, fn):
        self.callback = fn

    def ignore_types(self, *a, **k):
        pass


@pytest.fixture
def ports():
    return FakeOut(), FakeIn()


@pytest.fixture
def controller(ports):
    from pyflx4 import DDJFLX4

    out, inp = ports
    c = DDJFLX4(midi_out=out, midi_in=inp)
    out.sent.clear()  # drop the SysEx init burst
    return c


@pytest.fixture
def dj(controller):
    from pyflx4 import DDJFLX4Tools

    return DDJFLX4Tools(controller)
