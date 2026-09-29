from __future__ import annotations

import json
import os
import urllib.request

from agents.model_settings import ModelSettings

from agents import Agent, WebSearchTool, function_tool

INSTRUCTIONS = (
    "You are a research assistant. Given a search term, you search the web for that term and "
    "produce a concise summary of the results. The summary must be 2-3 paragraphs and less than 300 "
    "words. Capture the main points. Write succinctly, no need to have complete sentences or good "
    "grammar. This will be consumed by someone synthesizing a report, so its vital you capture the "
    "essence and ignore any fluff. Do not include any additional commentary other than the summary "
    "itself."
)

# You.com MCP search endpoint. The free profile is keyless; setting YDC_API_KEY
# switches to the authenticated profile. The server answers stateless tools/call
# requests, so a single POST is enough to run a search.
_YOUCOM_FREE_URL = "https://api.you.com/mcp?profile=free"
_YOUCOM_AUTH_URL = "https://api.you.com/mcp"
_YOUCOM_TIMEOUT_SECONDS = 30.0
_YOUCOM_MAX_RESULTS = 10
_YOUCOM_REQUEST_ID = 1


def _parse_youcom_response(body: str) -> list[dict]:
    """Extract the web hits from a You.com MCP tools/call response body."""
    result = None
    for line in body.splitlines():
        if line.startswith("data: "):
            message = json.loads(line[len("data: ") :])
            if message.get("id") == _YOUCOM_REQUEST_ID and "result" in message:
                result = message["result"]
    # Some gateways answer plain JSON instead of an SSE stream.
    if result is None and body.lstrip().startswith("{"):
        result = json.loads(body).get("result")
    if result is None or result.get("isError"):
        raise RuntimeError("You.com search returned an error")
    hits = json.loads(result["content"][0]["text"]).get("results", {}).get("web", [])
    return hits


def _format_youcom_hits(hits: list[dict]) -> str:
    """Render web hits as a compact numbered list for the search agent."""
    lines = []
    for rank, hit in enumerate(hits[:_YOUCOM_MAX_RESULTS], start=1):
        title = hit.get("title") or hit.get("url") or "untitled"
        url = hit.get("url", "")
        description = hit.get("description") or ""
        lines.append(f"{rank}. {title}\n{url}\n{description}".rstrip())
    return "\n\n".join(lines) if lines else "No results found."


def _youcom_search(query: str) -> list[dict]:
    """Call the You.com you-search MCP tool and return the web hits."""
    api_key = os.getenv("YDC_API_KEY")
    url = _YOUCOM_AUTH_URL if api_key else _YOUCOM_FREE_URL
    payload = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": _YOUCOM_REQUEST_ID,
            "method": "tools/call",
            "params": {"name": "you-search", "arguments": {"query": query}},
        }
    ).encode("utf-8")
    request = urllib.request.Request(url, data=payload, method="POST")
    request.add_header("Content-Type", "application/json")
    request.add_header("Accept", "application/json, text/event-stream")
    request.add_header(
        "User-Agent",
        "agentic-research (+https://github.com/BittnerPierre/agentic-research)",
    )
    if api_key:
        request.add_header("Authorization", f"Bearer {api_key}")
    with urllib.request.urlopen(request, timeout=_YOUCOM_TIMEOUT_SECONDS) as response:
        body = response.read().decode("utf-8")
    return _parse_youcom_response(body)


@function_tool
def youcom_search(query: str) -> str:
    """Search the web with You.com and return the top results (title, url, description).

    Use it to find current web sources for a research query. Works without an API
    key; set YDC_API_KEY to use the authenticated You.com profile.
    """

    return _format_youcom_hits(_youcom_search(query))


def create_search_agent(provider: str) -> Agent:
    """Build the web search agent for the given provider.

    "openai" (default behavior) uses the OpenAI WebSearchTool; "youcom" uses the
    You.com search tool (keyless free profile by default, or YDC_API_KEY for the
    authenticated profile).
    """
    if provider == "openai":
        tools = [WebSearchTool()]
    elif provider == "youcom":
        tools = [youcom_search]
    else:
        raise ValueError(f"Unknown web_search.provider: {provider}")

    return Agent(
        name="Search agent",
        instructions=INSTRUCTIONS,
        tools=tools,
        model_settings=ModelSettings(tool_choice="auto"),
    )


# Default OpenAI search agent, kept at module level for backward compatibility.
# The standard manager builds its own agent from web_search.provider in the config.
search_agent = create_search_agent("openai")
