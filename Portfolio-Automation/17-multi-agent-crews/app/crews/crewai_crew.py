"""The research team in CrewAI: 4 agents, sequential tasks."""

import time

from crewai import LLM, Agent, Crew, Process, Task
from crewai.events import crewai_event_bus
from crewai.events.types.llm_events import LLMCallCompletedEvent
from crewai.tools import tool

from app import config
from app.crews import prompts
from app.models import Report, build_report
from app.tools import calculate, search_corpus

# CrewOutput.token_usage.successful_requests double-counts (24 for 6 real calls), so count LLM events instead.
# ponytail: one process-wide counter; two crews running at the same time would mix their counts.
_calls = {"n": 0}


@crewai_event_bus.on(LLMCallCompletedEvent)
def _count_call(source, event) -> None:
    _calls["n"] += 1


def run(topic: str) -> Report:
    sources: set[str] = set()

    @tool("search_corpus")
    def search(query: str) -> str:
        """Search the market research corpus. Input: a few keywords."""
        return search_corpus(query, sources)

    @tool("calculate")
    def calc(expression: str) -> str:
        """Evaluate an arithmetic expression with + - * / and parentheses, e.g. (3600-1200)/1200."""
        return calculate(expression)

    llm = LLM(
        model=f"openai/{config.LLM_MODEL}", base_url=config.LLM_BASE_URL, api_key=config.LLM_API_KEY, temperature=0.2
    )

    def agent(role: str, goal: str, tools=()) -> Agent:
        return Agent(
            role=role,
            goal=goal,
            backstory=goal,
            tools=list(tools),
            llm=llm,
            allow_delegation=False,
            max_iter=4,
            verbose=False,
        )

    researcher = agent("Investigador", prompts.RESEARCHER, [search])
    analyst = agent("Analista", prompts.ANALYST, [calc])
    writer = agent("Redactor", prompts.WRITER)
    reviewer = agent("Revisor", prompts.REVIEWER)
    tasks = [
        Task(description=prompts.task(topic), expected_output="Datos con cifras y archivos citados", agent=researcher),
        Task(
            description="Analiza los datos de la investigación.", expected_output="Análisis con cálculos", agent=analyst
        ),
        Task(
            description="Redacta el informe.",
            expected_output="Informe Markdown con las secciones pedidas",
            agent=writer,
        ),
        Task(
            description="Revisa y entrega el informe final.", expected_output="Informe Markdown final", agent=reviewer
        ),
    ]

    start, calls_before = time.perf_counter(), _calls["n"]
    result = Crew(agents=[researcher, analyst, writer, reviewer], tasks=tasks, process=Process.sequential).kickoff()
    crewai_event_bus.flush()
    return build_report(topic, result.raw, sources, _calls["n"] - calls_before, time.perf_counter() - start)
