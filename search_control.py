"""
search_control.py — Web search for ORION MK2
──────────────────────────────────────────────
Uses DuckDuckGo (free, no API key needed) to fetch current
information, then passes the results to Ollama so Orion can
give a spoken, summarised answer.

pip install duckduckgo-search
──────────────────────────────────────────────
"""

from ddgs import DDGS

# Max number of search results to pass to Ollama.
# More = richer context but slower response.
MAX_RESULTS = 5


class SearchError(Exception):
    """Raised when a search operation fails."""


def search(query: str, max_results: int = MAX_RESULTS) -> list[dict]:
    """
    Search DuckDuckGo and return the top results.

    Returns a list of dicts:
        [{"title": str, "url": str, "body": str}, ...]
    """
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
        if not results:
            raise SearchError(f"No results found for '{query}'.")
        return results
    except Exception as e:
        raise SearchError(f"Search failed: {e}") from e



def format_results_for_prompt(query: str, results: list[dict]) -> str:
    """
    Format search results into a prompt snippet for Ollama.
    Keeps it concise so the model doesn't get overwhelmed.
    """
    lines = [
        f"The user asked: \"{query}\"",
        "Here are the top web search results:\n",
    ]
    for i, r in enumerate(results, 1):
        lines.append(f"[{i}] {r.get('title', '')}")
        lines.append(f"    {r.get('body', '')[:300]}")
        lines.append("")

    lines.append(
        "Based only on the above results, give a short spoken answer. "
        "Do not mention the search results directly. "
        "Speak naturally as ORION would — concise, helpful, addressed to 'sir'. "
        "If the results don't contain enough information to answer, say so."
    )

    return "\n".join(lines)