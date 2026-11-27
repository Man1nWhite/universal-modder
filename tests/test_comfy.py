"""`um comfy` builds and runs ComfyUI workflows locally; the graph is the product.

No server is needed to test graph construction, `--set` overrides, error formatting and output
naming — all pure or boundary-faked. Before this file, `um comfy` had no tests at all.
"""
from __future__ import annotations

import json

import pytest

from um import comfy


# --------------------------------------------------------------------------- txt2img graph


def test_txt2img_wires_the_stock_graph():
    wf = comfy.txt2img("a rusty drone", "sd_xl.safetensors", "blurry", 1024, 1024, 30, 7.0, 1234, "euler", "normal", 1)
    assert wf["4"]["inputs"]["ckpt_name"] == "sd_xl.safetensors"
    assert wf["6"]["inputs"]["text"] == "a rusty drone"
    assert wf["7"]["inputs"]["text"] == "blurry"
    assert wf["6"]["inputs"]["clip"] == ["4", 1]
    assert wf["3"]["inputs"]["model"] == ["4", 0]
    assert wf["3"]["inputs"]["positive"] == ["6", 0]
    assert wf["3"]["inputs"]["negative"] == ["7", 0]
    assert wf["3"]["inputs"]["latent_image"] == ["5", 0]
    assert wf["3"]["inputs"]["seed"] == 1234
    assert wf["5"]["inputs"] == {"width": 1024, "height": 1024, "batch_size": 1}
    assert wf["8"]["inputs"]["vae"] == ["4", 2]
    assert wf["9"]["inputs"]["images"] == ["8", 0]
    assert all("class_type" in n for n in wf.values())


# --------------------------------------------------------------------------- /object_info combos


def test_combo_classic_list():
    assert comfy._combo([["a.safetensors", "b.safetensors"], {"default": "a"}]) == ["a.safetensors", "b.safetensors"]


def test_combo_v3_options():
    assert comfy._combo(["COMBO", {"options": ["x", "y"]}]) == ["x", "y"]


def test_combo_weird_input_is_empty():
    assert comfy._combo([]) == [] and comfy._combo("nope") == []


# --------------------------------------------------------------------------- load_workflow


def _write(tmp_path, name, data):
    p = tmp_path / name
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


def test_load_workflow_accepts_api_format(tmp_path):
    wf = {"1": {"class_type": "KSampler", "inputs": {}}}
    assert comfy.load_workflow(_write(tmp_path, "ok.json", wf)) == wf


def test_load_workflow_unwraps_a_prompt_envelope(tmp_path):
    wf = {"1": {"class_type": "KSampler", "inputs": {}}}
    assert comfy.load_workflow(_write(tmp_path, "env.json", {"prompt": wf})) == wf


def test_load_workflow_refuses_a_ui_export(tmp_path, capsys):
    ui = _write(tmp_path, "ui.json", {"nodes": [], "links": []})
    with pytest.raises(SystemExit):
        comfy.load_workflow(ui)
    assert "Export (API)" in capsys.readouterr().err


def test_load_workflow_refuses_junk(tmp_path):
    bad = _write(tmp_path, "bad.json", ["not", "a", "dict"])
    with pytest.raises(SystemExit):
        comfy.load_workflow(bad)


# --------------------------------------------------------------------------- apply_set


def _wf():
    return {
        "6": {"class_type": "CLIPTextEncode", "inputs": {"text": "old"}, "_meta": {"title": "Positive Prompt"}},
        "10": {"class_type": "SaveImage", "inputs": {}},
    }


def test_apply_set_by_node_id():
    wf = comfy.apply_set(_wf(), ["6.text=a drone"])
    assert wf["6"]["inputs"]["text"] == "a drone"


def test_apply_set_by_title_is_case_insensitive():
    wf = comfy.apply_set(_wf(), ["positive prompt.text=a drone"])
    assert wf["6"]["inputs"]["text"] == "a drone"


def test_apply_set_json_value():
    wf = comfy.apply_set(_wf(), ["10.filename_prefix:=\"um_test\"", "6.text:=123"])
    assert wf["10"]["inputs"]["filename_prefix"] == "um_test"
    assert wf["6"]["inputs"]["text"] == 123


def test_apply_set_does_not_mutate_the_input():
    wf = _wf()
    comfy.apply_set(wf, ["6.text=changed"])
    assert wf["6"]["inputs"]["text"] == "old"


def test_apply_set_rejects_bad_specs():
    with pytest.raises(SystemExit):
        comfy.apply_set(_wf(), ["no-dot-here"])
    with pytest.raises(SystemExit):
        comfy.apply_set(_wf(), ["6.text:={not json"])


def test_apply_set_dies_on_unknown_or_ambiguous_node():
    with pytest.raises(SystemExit):
        comfy.apply_set(_wf(), ["nosuchnode.text=x"])
    dup = _wf()
    dup["7"] = {"class_type": "CLIPTextEncode", "inputs": {}, "_meta": {"title": "Positive Prompt"}}
    with pytest.raises(SystemExit):
        comfy.apply_set(dup, ["positive prompt.text=x"])


# --------------------------------------------------------------------------- error formatting and outputs


def test_describe_flattens_node_errors():
    err = {"error": {"message": "invalid", "details": "bad input"},
           "node_errors": {"3": {"class_type": "KSampler", "errors": [{"message": "seed is required", "details": ""}]}}}
    out = comfy._describe(err)
    assert "invalid bad input" in out
    assert "node 3 (KSampler): seed is required" in out


def test_outputs_collects_files_in_node_order():
    history = {"outputs": {
        "9": {"images": [{"filename": "um_00001_.png", "subfolder": "", "type": "output"}]},
        "12": {"images": [{"filename": "um_00002_.png", "subfolder": "sub", "type": "temp"}]},
    }}
    files = comfy.outputs(history)
    assert [f["filename"] for f in files] == ["um_00001_.png", "um_00002_.png"]


def test_base_url_prefers_the_flag_over_env(monkeypatch):
    monkeypatch.setenv("COMFYUI_URL", "http://10.0.0.5:8188/")
    assert comfy.base_url("http://10.0.0.9:8188/") == "http://10.0.0.9:8188"
    assert comfy.base_url() == "http://10.0.0.5:8188"


def test_name_comes_from_the_prompt():
    assert comfy._name(type("A", (), {"name": None}), "A Rusty Drone! Sprite") == "a_rusty_drone_sprite"
    assert comfy._name(type("A", (), {"name": "chosen"}), "ignored") == "chosen"
