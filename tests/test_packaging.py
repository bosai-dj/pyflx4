"""Packaging promises, checked rather than asserted in a README.

Each of these is a claim the project makes to someone who has not read the source:
that annotations reach their type checker, that installing this pulls in one thing
and not a tree, that the version a bug report quotes matches what was published,
and that every Python version the metadata advertises is actually run.
"""

import pathlib

import tomllib

import pyflx4

ROOT = pathlib.Path(__file__).resolve().parent.parent
PYPROJECT = tomllib.loads((ROOT / "pyproject.toml").read_text())


def test_py_typed_marker_ships_inside_the_package():
    """PEP 561: without this file INSIDE the installed package, every annotation
    here is invisible to a consumer's type checker and `Typing :: Typed` is a lie."""
    assert (ROOT / "src" / "pyflx4" / "py.typed").is_file()


def test_version_is_stated_once_as_far_as_anyone_can_tell():
    """The version lives in pyproject.toml and in __version__, and the wheel's
    metadata comes from the first while the release workflow checks the tag against
    the second. If they disagree, a release publishes one number and reports another.
    """
    assert PYPROJECT["project"]["version"] == pyflx4.__version__


def test_dependency_list_is_exactly_the_midi_bindings():
    """python-rtmidi is the one dependency, and it is a compiled one — on some
    platforms it needs system headers to build. A second entry here is a real cost
    to every consumer, so adding one should be deliberate rather than incidental."""
    assert PYPROJECT["project"]["dependencies"] == ["python-rtmidi>=1.5.8"]


def test_every_advertised_python_version_is_actually_tested():
    """The classifiers are a promise CI has to keep. python-rtmidi has no Linux
    wheels for the newest versions and builds from source there, which is exactly
    the kind of breakage that only shows up if the version is really run."""
    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text()
    advertised = [
        c.rsplit(" :: ", 1)[-1]
        for c in PYPROJECT["project"]["classifiers"]
        if c.startswith("Programming Language :: Python :: 3.")
    ]
    assert advertised, "no Python version classifiers declared"
    untested = [v for v in advertised if f"'{v}'" not in ci]
    assert not untested, f"classifiers advertise {untested}; CI does not run them"


def test_requires_python_floor_matches_the_lowest_advertised_version():
    floor = PYPROJECT["project"]["requires-python"].lstrip(">=")
    advertised = sorted(
        (
            c.rsplit(" :: ", 1)[-1]
            for c in PYPROJECT["project"]["classifiers"]
            if c.startswith("Programming Language :: Python :: 3.")
        ),
        key=lambda v: tuple(int(p) for p in v.split(".")),
    )
    assert advertised[0] == floor
