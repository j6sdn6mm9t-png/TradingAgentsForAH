"""Optional bridge from a local research run to the Web dashboard API."""

import json
from typing import Any, Dict
from urllib.parse import urlparse
from urllib.request import ProxyHandler, Request, build_opener, urlopen

from .domain import ResearchState


def _open(request: Request, timeout_seconds: float):
    hostname = urlparse(request.full_url).hostname
    if hostname in {"localhost", "127.0.0.1", "::1"}:
        return build_opener(ProxyHandler({})).open(request, timeout=timeout_seconds)
    return urlopen(request, timeout=timeout_seconds)


def sync_research_run(
    state: ResearchState,
    base_url: str = "http://localhost:3000",
    timeout_seconds: float = 10.0,
) -> Dict[str, Any]:
    if state.synthesis is None or state.valuation is None:
        raise ValueError("cannot sync an incomplete research state")
    payload = json.dumps(state.to_dict(), ensure_ascii=False).encode("utf-8")
    request = Request(
        f"{base_url.rstrip('/')}/api/research",
        data=payload,
        headers={"content-type": "application/json", "accept": "application/json"},
        method="POST",
    )
    with _open(request, timeout_seconds) as response:
        return json.loads(response.read().decode("utf-8"))
