from unittest.mock import MagicMock

import pytest

from reachy_mini_conversation_app.tools.core_tools import ToolDependencies
from reachy_mini_conversation_app.tools.research_question import ResearchQuestion


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "question,search_web",
    [
        ("Why are only some areas uncut?", False),
        ("Tell me about the Yom Kippur War.", False),
        ("Look up the causes of the Yom Kippur War.", True),
    ],
)
async def test_research_tool_acknowledges_without_waiting_for_inference(question, search_web):
    """The voice tool delegates synchronously and returns a conversational next step."""
    request = MagicMock(return_value={"status": "researching", "instruction": "Ask a useful clarification."})
    deps = ToolDependencies(reachy_mini=MagicMock(), movement_manager=MagicMock(), request_research=request)
    result = await ResearchQuestion()(deps, question=question, search_web=search_web)
    assert result["status"] == "researching"
    request.assert_called_once_with(question, search_web)


@pytest.mark.asyncio
async def test_research_tool_handles_unavailable_and_empty_requests():
    """Missing setup and invalid input produce recoverable errors."""
    deps = ToolDependencies(reachy_mini=MagicMock(), movement_manager=MagicMock())
    assert "unavailable" in (await ResearchQuestion()(deps, question="Why?"))["error"]
    assert "error" in await ResearchQuestion()(deps, question="  ")
