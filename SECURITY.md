# Security policy

## Supported versions

Only the latest released version receives fixes. This is a 0.x library; there are no
maintenance branches.

## Reporting a vulnerability

Report privately via
[GitHub Security Advisories](https://github.com/bosai-dj/pyflx4/security/advisories/new).
Please do not open a public issue.

Expect an acknowledgement within 7 days. This is a small project with no dedicated
security staffing, so that window is what can actually be met rather than an aspiration.

## Scope

pyflx4 opens a USB MIDI port and exchanges short messages with a DJ controller. It makes
no network calls, reads no files, and executes nothing it receives. Its one dependency is
`python-rtmidi`, which is where the actual parsing of untrusted device input happens — a
malicious or malfunctioning USB device is that project's threat model more than this
one's.

What is in scope here:

- **Input decoding.** `_on_midi_in` parses whatever arrives on the port. Malformed or
  hostile messages should not crash a caller's process or corrupt state; short messages
  and unknown notes are handled, and there are tests for both.
- **The SysEx init sequence**, which is sent to any port whose name matches `DDJ-FLX4`.

Note that a wrong mapping value is a correctness bug, not a security one, however
annoying it is mid-set. Report those as ordinary issues.
