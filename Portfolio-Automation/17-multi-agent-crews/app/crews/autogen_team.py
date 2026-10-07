"""The same research team in AutoGen 0.4+ (agentchat): round-robin group chat."""

import asyncio
import time

from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.conditions import MaxMessageTermination, TextMentionTermination
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_ext.models.openai import OpenAIChatCompletionClient

from app import config
from app.crews import prompts
from app.models import Report, build_report
from app.tools import calculate, search_corpus


def run(topic: str) -> Report:
    return asyncio.run(_run(topic))


async def _run(topic: str) -> Report:
    sources: set[str] = set()

    def search_corpus_tool(query: str) -> str:
        """Search the market research corpus. Input: a few keywords."""
        return search_corpus(query, sources)

    def calculate_tool(expression: str) -> str:
        """Evaluate an arithmetic expression with + - * / and parentheses, e.g. (3600-1200)/1200."""
        return calculate(expression)

    search_corpus_tool.__name__, calculate_tool.__name__ = "search_corpus", "calculate"  # names the prompts use
    client = OpenAIChatCompletionClient(
        model=config.LLM_MODEL,
        base_url=config.LLM_BASE_URL,
        api_key=config.LLM_API_KEY,
        temperature=0.2,
        model_info={
            "vision": False,
            "function_calling": True,
            "json_output": False,
            "family": "unknown",
            "structured_output": False,
        },
    )
    team = RoundRobinGroupChat(
        [
            AssistantAgent(
                "Investigador",
                client,
                tools=[search_corpus_tool],
                reflect_on_tool_use=True,
                system_message=prompts.RESEARCHER,
            ),
            AssistantAgent(
                "Analista", client, tools=[calculate_tool], reflect_on_tool_use=True, system_message=prompts.ANALYST
            ),
            AssistantAgent("Redactor", client, system_message=prompts.WRITER),
            AssistantAgent("Revisor", client, system_message=prompts.REVIEWER + " Termina con la palabra TERMINATE."),
        ],
        termination_condition=TextMentionTermination("TERMINATE") | MaxMessageTermination(12),
    )

    start = time.perf_counter()
    try:
        result = await team.run(task=prompts.task(topic))
    finally:
        await client.close()
    final = next(
        (m.content for m in reversed(result.messages) if m.source == "Revisor" and isinstance(m.content, str)), ""
    )
    calls = sum(1 for m in result.messages if getattr(m, "models_usage", None))  # one per model response
    return build_report(topic, final, sources, calls, time.perf_counter() - start)
