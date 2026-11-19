import logging

from reachy_mini_conversation_app.tools.core_tools import Tool, ToolDependencies


logger = logging.getLogger(__name__)


class ResearchQuestion(Tool):
    """Delegate a question on any topic without waiting for research."""

    name = "research_question"
    description = (
        "Answer established facts and requests to brainstorm directly. Use this tool for uncertain specifics, "
        "current facts, explicit lookups, or explanations needing research and synthesis, on ANY topic. "
        "History, science, art, current events, and project context are welcome. "
        "The advisor can research the web. This tool returns immediately, not the answer. "
        "Set search_web=true when the user requests a lookup, current information, or sources. "
        "Acknowledge once, then respond naturally to the student's actual comments using established context. "
        "Discuss their ideas, label brainstorming as suggestions, and use light situational humor when it fits. "
        "Ask only useful questions; do not repeat waiting messages or fill every silence. Follow interruptions. "
        "Do not guess the unresolved fact, invent projects, names, dates or sources, or claim research is verified "
        "before its note arrives. Connect the findings to the latest conversation only when still relevant. "
        "Write the question in the student's own words; never add, guess, or change years or dates "
        "(keep 'this year' as said). Do not redirect unrelated topics to laser cutting. "
        "Call again only for a new question or information that changes the research; never poll this tool."
    )
    parameters_schema = {
        "type": "object",
        "properties": {
            "question": {"type": "string", "description": "The unresolved question and relevant known facts."},
            "search_web": {
                "type": "boolean",
                "description": "Require an internet search for a lookup, current facts, or sources.",
            },
        },
        "required": ["question"],
        "additionalProperties": False,
    }

    async def __call__(self, deps: ToolDependencies, **kwargs: object) -> dict[str, str]:
        """Queue research and immediately return the conversational next step."""
        question = kwargs.get("question")
        if not isinstance(question, str) or not question.strip():
            logger.warning("research_question: missing question")
            return {"error": "A nonempty research question is required."}
        if deps.request_research is None:
            return {
                "error": "Research is unavailable. Say so briefly; do not claim to have searched. Offer known facts with uncertainty."
            }
        search_web = kwargs.get("search_web", False)
        if not isinstance(search_web, bool):
            return {"error": "search_web must be true or false."}
        return deps.request_research(question, search_web)
