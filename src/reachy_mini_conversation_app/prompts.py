"""Resolve active profile prompts and voice settings."""

import logging
from pathlib import Path

from reachy_mini_conversation_app.config import PROJECT_ROOT, config, get_default_voice
from reachy_mini_conversation_app.memory import format_memory_for_prompt
from reachy_mini_conversation_app.profile_store import (
    DEFAULT_PROFILE_NAME,
    ProfileDefinition,
    ProfileFormatError,
    read_profile,
    read_packaged_default_profile,
)


logger = logging.getLogger(__name__)

DEFAULT_GREETING_PROMPT = (
    "Start the conversation now with a brief, spontaneous greeting in character. "
    "Keep it to one sentence, invite the user in naturally, and vary the wording each time."
)


def _active_profile() -> ProfileDefinition:
    return read_profile(config.REACHY_MINI_CUSTOM_PROFILE)


def read_grounding_document(filename: str, setting: str) -> str:
    """Read a nonempty UTF-8 grounding file relative to the project root."""
    path = Path(filename).expanduser()
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    try:
        grounding = path.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeError) as exc:
        raise RuntimeError(f"Cannot read {setting} at {path}: {exc}") from exc
    if not grounding:
        raise RuntimeError(f"{setting} is empty: {path}")
    logger.info("Loaded %s from %s (%d characters)", setting, path, len(grounding))
    return grounding


def get_session_instructions(instance_path: str | Path | None = None) -> str:
    """Return active profile instructions with local grounding and memory context."""
    selected_profile = config.REACHY_MINI_CUSTOM_PROFILE
    profile_name = selected_profile or DEFAULT_PROFILE_NAME
    try:
        profile = _active_profile()
        instructions = profile.instructions.strip()
    except (FileNotFoundError, ProfileFormatError) as exc:
        logger.warning("Failed to load profile %r: %s", profile_name, exc)
        instructions = ""

    if not instructions and selected_profile and selected_profile != DEFAULT_PROFILE_NAME:
        logger.warning("Using bundled default instructions because profile %r is incomplete", selected_profile)
        try:
            instructions = read_packaged_default_profile().instructions.strip()
        except (FileNotFoundError, ProfileFormatError) as exc:
            raise RuntimeError("Default profile has no usable instructions") from exc
    if not instructions:
        raise RuntimeError("Default profile has no usable instructions")

    if config.GROUNDING_FILE:
        grounding = read_grounding_document(config.GROUNDING_FILE, "REACHY_MINI_GROUNDING_FILE")
        instructions += (
            "\n\n## LOCAL GROUNDING CONTEXT\n"
            "Use the following document for your identity, location, local facts, and shop rules. "
            "It takes precedence over conflicting personality text or remembered facts. "
            "Do not invent missing shop information or infer staff approval from this document; "
            "refer uncertain shop operating procedures and approvals to staff. "
            "This document defines local expertise, not a restriction on conversation topics. "
            "Answer general questions and use available research tools for information beyond it.\n\n"
            f"{grounding}"
        )

    memory_prompt = format_memory_for_prompt(instance_path)
    if memory_prompt:
        return f"{memory_prompt}\n\n{instructions}"
    return instructions


def get_session_voice(default: str | None = None) -> str:
    """Return the active profile voice or the backend default."""
    fallback = get_default_voice() if default is None else default
    try:
        return _active_profile().voice or fallback
    except (FileNotFoundError, ProfileFormatError) as exc:
        logger.warning("Failed to load the active profile voice: %s", exc)
        return fallback


def get_session_greeting_prompt() -> str:
    """Return the active profile greeting prompt or the app default."""
    try:
        return _active_profile().greeting or DEFAULT_GREETING_PROMPT
    except (FileNotFoundError, ProfileFormatError) as exc:
        logger.warning("Failed to load the active profile greeting: %s", exc)
        return DEFAULT_GREETING_PROMPT
