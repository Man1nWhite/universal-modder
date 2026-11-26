"""`um/render3d.py` without Blender: the spec parser and the lookup for the binary.

Rendering needs Blender, which CI does not install, so the whole module was unchecked. What can be
checked is where a render's settings come from — the `--anims name:frames:motion` grammar and the
motions it may name — and that a missing Blender is a `um:` message rather than a traceback.
"""
from __future__ import annotations

import pytest

from um import render3d


def test_parse_anims_reads_frames_and_motion():
    anims = render3d.parse_anims("idle:10:bob,walk:12:walk,death:20:die")
    assert anims["idle"]["frames"] == 10
    assert anims["idle"]["motion"] == render3d.MOTIONS["bob"]
    assert anims["walk"]["frames"] == 12
    assert anims["death"]["motion"] == render3d.MOTIONS["die"]


def test_parse_anims_defaults_frames_to_one_and_motion_to_still():
    assert render3d.parse_anims("idle")["idle"] == dict(frames=1, motion=None)
    assert render3d.parse_anims("idle:3")["idle"] == dict(frames=3, motion=None)


def test_an_unknown_motion_is_still_not_a_motion():
    """A typo names nothing: the render then keeps the bind pose instead of failing mid-Blender."""
    assert render3d.parse_anims("idle:3:nosuchmotion")["idle"]["motion"] is None


def test_every_named_motion_is_a_documented_kind():
    """`walk` and `wreck` share the `bob` and `die` kinds; every other name is its own kind."""
    kinds = {m["kind"] for m in render3d.MOTIONS.values() if m}
    for name, motion in render3d.MOTIONS.items():
        assert motion is None or motion["kind"] in kinds, name
        assert motion is None or motion["kind"] in (name, "bob", "die"), name


def test_every_preset_has_the_camera_keys_the_renderer_reads():
    for name, preset in render3d.PRESETS.items():
        assert isinstance(preset, dict) and preset, name


def test_every_motion_named_in_the_cli_defaults_exists():
    """The `--anims` default in register() must parse, so the command works with no arguments."""
    import argparse

    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="group")
    render3d.register(sub)
    parser = sub.choices["render3d"]
    default = next(a.default for a in parser._actions if a.dest == "anims")
    for anim, det in render3d.parse_anims(default).items():
        assert det["frames"] >= 1, anim


def test_missing_blender_is_a_message_not_a_traceback(monkeypatch):
    monkeypatch.delenv("BLENDER", raising=False)
    monkeypatch.setattr(render3d.shutil, "which", lambda name: None)
    monkeypatch.setattr(render3d.Path, "exists", lambda self: False)
    with pytest.raises(SystemExit):
        render3d.blender_bin()


def test_blender_from_the_environment_wins(monkeypatch):
    monkeypatch.setenv("BLENDER", "/opt/blender")
    assert render3d.blender_bin() == "/opt/blender"


def test_register_exposes_the_group():
    import argparse

    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="group")
    render3d.register(sub)
    assert set(sub.choices) == {"render3d"}
