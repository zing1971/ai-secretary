"""
Web 搜尋技能：搜尋網路資訊。
"""

import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))

from web_service import web_search as _web_search


def search_web(query: str, max_results: int = 5) -> str:
    """
    搜尋網路上的即時資訊。

    Args:
        query: 搜尋關鍵字或問題（必填）。
        max_results: 最多回傳幾筆結果（預設 5）。
    """
    results = _web_search(query, max_results)
    if not results:
        return f"找不到「{query}」的搜尋結果。"

    lines = []
    for i, r in enumerate(results, 1):
        lines.append(
            f"{i}. {r['title']}\n"
            f"   {r['url']}\n"
            f"   {r['snippet']}"
        )
    return "\n\n".join(lines)
