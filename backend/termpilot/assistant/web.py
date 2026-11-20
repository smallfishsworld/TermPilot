"""Web search through the Serper API."""

from __future__ import annotations

from dataclasses import dataclass, field

import requests

from termpilot.errors import FeatureUnavailable, UpstreamFailure
from termpilot.settings import Settings


@dataclass(frozen=True)
class WebResult:
    title: str
    url: str
    snippet: str


@dataclass
class WebResults:
    results: list[WebResult] = field(default_factory=list)
    related_questions: list[str] = field(default_factory=list)


def search(settings: Settings, query: str, *, count: int = 8, language: str = "en") -> WebResults:
    if settings.web_search_api_key is None:
        raise FeatureUnavailable("Web search needs TP_WEB_SEARCH_API_KEY.")
    try:
        response = requests.post(
            f"{settings.web_search_url}/search",
            headers={"X-API-KEY": settings.web_search_api_key.get_secret_value()},
            json={"q": query, "num": count, "hl": language},
            timeout=20,
        )
        response.raise_for_status()
        body = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise UpstreamFailure("The web search service did not respond.") from exc
    return WebResults(
        results=[
            WebResult(
                title=str(item.get("title") or item.get("link")),
                url=str(item["link"]),
                snippet=str(item.get("snippet") or ""),
            )
            for item in body.get("organic", [])
            if item.get("link")
        ][:count],
        related_questions=[str(item["question"]) for item in body.get("peopleAlsoAsk", []) if item.get("question")][:3],
    )
