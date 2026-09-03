from __future__ import annotations

from agents.model_settings import ModelSettings
from tavily import TavilyClient

from agents import Agent, WebSearchTool, tool

INSTRUCTIONS = (
    "You are a research assistant. Given a search term, you search the web for that term and "
    "produce a concise summary of the results. The summary must be 2-3 paragraphs and less than 300 "
    "words. Capture the main points. Write succinctly, no need to have complete sentences or good "
    "grammar. This will be consumed by someone synthesizing a report, so its vital you capture the "
    "essence and ignore any fluff. Do not include any additional commentary other than the summary "
    "itself."
)


@tool
def tavily_search(query: str) -> str:
    """Search the web using Tavily and return a summary of results.

    Args:
        query: The search query string.

    Returns:
        A formatted string containing the search results.
    """
    client = TavilyClient()
    response = client.search(
        query=query,
        max_results=5,
        search_depth="advanced",
        topic="general",
    )
    parts: list[str] = []
    for result in response.get("results", []):
        title = result.get("title", "")
        content = result.get("content", "")
        url = result.get("url", "")
        parts.append(f"**{title}**\n{content}\nSource: {url}")
    return "\n\n".join(parts) if parts else "No results found."


search_agent = Agent(
    name="Search agent",
    instructions=INSTRUCTIONS,
    tools=[WebSearchTool()],
    model_settings=ModelSettings(tool_choice="auto"),
)


def create_search_agent(provider: str = "openai") -> Agent:
    """Create a search agent configured for the given web search provider.

    Args:
        provider: Either 'openai' (Bing-backed WebSearchTool) or 'tavily'.

    Returns:
        An Agent configured with the appropriate search tool.
    """
    if provider == "tavily":
        return Agent(
            name="Search agent",
            instructions=INSTRUCTIONS,
            tools=[tavily_search],
            model_settings=ModelSettings(tool_choice="auto"),
        )
    return Agent(
        name="Search agent",
        instructions=INSTRUCTIONS,
        tools=[WebSearchTool()],
        model_settings=ModelSettings(tool_choice="auto"),
    )
