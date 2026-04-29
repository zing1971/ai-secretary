"""
郵件消化技能：批次搜尋信件並逐封摘要。
"""

import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))

from _skill_base import _GMAIL_IDX, _require_service
from gmail_service import get_recent_emails
from summarize_skills import summarize_text


def digest_emails(query: str = "is:unread", max_results: int = 5) -> str:
    """
    搜尋信件並對每封產生 Gemini 摘要。

    Args:
        query: Gmail 搜尋條件（預設 "is:unread"）。
        max_results: 最多處理幾封（預設 5）。
    """
    service = _require_service(_GMAIL_IDX, "Gmail")
    emails = get_recent_emails(service, query, max_results)

    if not emails:
        return "📧 沒有符合條件的信件"

    lines = [f"📧 郵件摘要（{len(emails)} 封）\n"]
    for i, e in enumerate(emails, 1):
        content = f"寄件人：{e['sender']}\n主旨：{e['subject']}\n\n{e['body']}"
        summary = summarize_text(content)
        lines.append(
            f"{i}. [{e['sender'][:30]}]\n"
            f"   主旨：{e['subject']}\n"
            f"   摘要：{summary}\n"
            f"   連結：{e['url']}"
        )

    return "\n\n".join(lines)
