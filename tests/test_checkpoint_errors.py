"""Checkpoint-missing errors should be actionable. python -m pytest tests/test_checkpoint_errors.py -v"""
import os

import pytest
import torch
from nanochat.checkpoint_manager import _modal_suggestion, load_model


def test_missing_base_checkpoints_message(tmp_path, monkeypatch):
    monkeypatch.setenv("NANOCHAT_BASE_DIR", str(tmp_path))
    with pytest.raises(FileNotFoundError) as e:
        load_model("base", torch.device("cpu"), phase="eval")
    msg = str(e.value)
    assert str(tmp_path / "base_checkpoints") in msg
    assert "'base'" in msg and "base_train" in msg and "RUNNING.md" in msg


def test_missing_sft_hint(tmp_path, monkeypatch):
    monkeypatch.setenv("NANOCHAT_BASE_DIR", str(tmp_path))
    with pytest.raises(FileNotFoundError, match="chat_sft"):
        load_model("sft", torch.device("cpu"), phase="eval")


# --- _modal_suggestion ---

# Scenario: no Modal cache directory exists; suggestion must be empty to avoid spurious hints.
def test_modal_suggestion_empty_when_no_cache(tmp_path, monkeypatch):
    # Given HOME has no .cache/nanochat-modal tree
    monkeypatch.setenv("HOME", str(tmp_path))
    # When asked for a base suggestion
    result = _modal_suggestion("base")
    # Then nothing is suggested
    assert result == ""


# Scenario: Modal CPU artifacts are present; suggestion should point at chat_cli.
def test_modal_suggestion_cpu_hint(tmp_path, monkeypatch):
    # Given ~/.cache/nanochat-modal/cpu/base_checkpoints/ exists
    cache = tmp_path / ".cache" / "nanochat-modal" / "cpu" / "base_checkpoints"
    cache.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(tmp_path))
    # When asked for a base suggestion
    result = _modal_suggestion("base")
    # Then the hint names CPU and chat_cli
    assert "CPU" in result
    assert "chat_cli" in result


# Scenario: GPU artifacts present; hint should say GPU.
def test_modal_suggestion_gpu_hint(tmp_path, monkeypatch):
    # Given ~/.cache/nanochat-modal/gpu/base_checkpoints/ exists
    cache = tmp_path / ".cache" / "nanochat-modal" / "gpu" / "base_checkpoints"
    cache.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(tmp_path))
    result = _modal_suggestion("base")
    assert "GPU" in result


# Scenario: unknown source (typo, unsupported stage); must return empty string not raise.
def test_modal_suggestion_unknown_source_is_empty():
    result = _modal_suggestion("unknown_stage")
    assert result == ""
