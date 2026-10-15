"""Tests for loading local grounding into conversational instructions."""

from pathlib import Path

import pytest

from reachy_mini_conversation_app import prompts
from reachy_mini_conversation_app.config import config


@pytest.mark.parametrize("relative", [False, True])
def test_grounding_is_combined_with_profile_and_memory_and_reread(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, relative: bool
) -> None:
    """Grounding survives a different working directory and picks up document edits."""
    document = tmp_path / "shop context.md"
    document.write_text("You are Ari. Staff must approve materials.", encoding="utf-8")
    monkeypatch.setattr(prompts, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(config, "GROUNDING_FILE", document.name if relative else str(document))
    monkeypatch.setattr(config, "REACHY_MINI_CUSTOM_PROFILE", None)
    monkeypatch.setattr(prompts, "format_memory_for_prompt", lambda _path: "The student is a beginner.")
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)

    instructions = prompts.get_session_instructions(tmp_path)

    assert "The student is a beginner." in instructions
    assert "TOOL & MOVEMENT RULES" in instructions
    assert document.read_text(encoding="utf-8") in instructions

    document.write_text("You are Ari. Ask shop staff for help.", encoding="utf-8")
    refreshed = prompts.get_session_instructions(tmp_path)

    assert "Ask shop staff for help." in refreshed
    assert "Staff must approve materials." not in refreshed


@pytest.mark.parametrize("contents", [None, b" \n", b"\xff"])
def test_unusable_grounding_does_not_silently_start_an_ungrounded_session(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, contents: bytes | None
) -> None:
    """A configured missing, empty or non-UTF-8 document produces an actionable error."""
    document = tmp_path / "shop.md"
    if contents is not None:
        document.write_bytes(contents)
    monkeypatch.setattr(config, "GROUNDING_FILE", str(document))
    monkeypatch.setattr(config, "REACHY_MINI_CUSTOM_PROFILE", None)

    with pytest.raises(RuntimeError, match="REACHY_MINI_GROUNDING_FILE.*shop.md"):
        prompts.get_session_instructions(tmp_path)
