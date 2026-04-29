"""
Web Search 服務模組 — 使用 DuckDuckGo Search（不需 API key）。
"""
import logging

logger = logging.getLogger(__name__)

_MAX_SNIPPET = 300


def web_search(query: str, max_results: int = 5) -> list[dict]:
    """
    使用 DuckDuckGo 搜尋網路，回傳結果列表。

    Returns:
        list of dict: [{title, url, snippet}]

    Raises:
        RuntimeError: 套件未安裝或搜尋失敗。
    """
    try:
        from duckduckgo_search import DDGS
    except ImportError:
        raise RuntimeError(
            "缺少 duckduckgo-search 套件，請執行：pip install duckduckgo-search"
        )

    try:
        with DDGS() as ddgs:
            raw = list(ddgs.text(query, max_results=max_results))
    except Exception as exc:
        raise RuntimeError(f"Web 搜尋失敗：{exc}") from exc

    results = [
        {
            "title": r.get("title", ""),
            "url": r.get("href", ""),
            "snippet": r.get("body", "")[:_MAX_SNIPPET],
        }
        for r in raw
    ]
    logger.info("🔍 Web 搜尋 '%s'：找到 %d 筆結果", query, len(results))
    return results
