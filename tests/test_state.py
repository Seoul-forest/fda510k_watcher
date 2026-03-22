"""Tests for state management functions: load_state / save_state."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import fda_510k_html_watch as module


def test_load_state_returns_default_when_file_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(module, "STATE_FILE", tmp_path / "state.json")
    state = module.load_state()
    assert state == {"seen_k_numbers": []}


def test_load_state_reads_existing_file(tmp_path, monkeypatch):
    state_file = tmp_path / "state.json"
    data = {"seen_k_numbers": ["K240001", "K240002"]}
    state_file.write_text(json.dumps(data))
    monkeypatch.setattr(module, "STATE_FILE", state_file)

    state = module.load_state()
    assert state["seen_k_numbers"] == ["K240001", "K240002"]


def test_save_state_creates_file(tmp_path, monkeypatch):
    state_file = tmp_path / "state.json"
    monkeypatch.setattr(module, "STATE_FILE", state_file)

    module.save_state({"seen_k_numbers": ["K240001"]})

    assert state_file.exists()


def test_save_state_writes_valid_json(tmp_path, monkeypatch):
    state_file = tmp_path / "state.json"
    monkeypatch.setattr(module, "STATE_FILE", state_file)

    module.save_state({"seen_k_numbers": ["K240001", "K240002"]})

    content = json.loads(state_file.read_text())
    assert content["seen_k_numbers"] == ["K240001", "K240002"]


def test_save_and_load_round_trip(tmp_path, monkeypatch):
    state_file = tmp_path / "state.json"
    monkeypatch.setattr(module, "STATE_FILE", state_file)

    original = {"seen_k_numbers": ["K240001", "K240002", "K240003"]}
    module.save_state(original)
    loaded = module.load_state()

    assert loaded == original


def test_save_state_overwrites_existing(tmp_path, monkeypatch):
    state_file = tmp_path / "state.json"
    monkeypatch.setattr(module, "STATE_FILE", state_file)

    module.save_state({"seen_k_numbers": ["K240001"]})
    module.save_state({"seen_k_numbers": ["K240002", "K240003"]})

    loaded = module.load_state()
    assert loaded["seen_k_numbers"] == ["K240002", "K240003"]


def test_load_state_empty_seen_list(tmp_path, monkeypatch):
    state_file = tmp_path / "state.json"
    state_file.write_text(json.dumps({"seen_k_numbers": []}))
    monkeypatch.setattr(module, "STATE_FILE", state_file)

    state = module.load_state()
    assert state["seen_k_numbers"] == []


def test_load_state_corrupted_json_resets(tmp_path, monkeypatch):
    state_file = tmp_path / "state.json"
    state_file.write_text("{corrupted json!!!")
    monkeypatch.setattr(module, "STATE_FILE", state_file)

    state = module.load_state()
    assert state == {"seen_k_numbers": []}
    assert (tmp_path / "state.json.bak").exists()
    assert not state_file.exists()


def test_save_state_atomic_write(tmp_path, monkeypatch):
    state_file = tmp_path / "state.json"
    monkeypatch.setattr(module, "STATE_FILE", state_file)

    module.save_state({"seen_k_numbers": ["K240001"]})

    assert state_file.exists()
    assert not (tmp_path / "state.tmp").exists()
