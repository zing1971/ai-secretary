"""
Gmail 技能：搜尋近期信件、建立草稿。
"""

from _skill_base import _GMAIL_IDX, _require_service
from gmail_service import create_gmail_draft as _create_gmail_draft
from gmail_service import get_recent_emails as _get_recent_emails


def search_recent_gmails(query: str = None, max_results: int = 10) -> str:
    """
    搜尋並取得近期的 Gmail 信件。

    Args:
        query: Gmail 搜尋語法，例如 "is:unread" 或 "from:boss@example.com"。
               若不提供，預設搜尋近 3 天未讀信件。
        max_results: 最多回傳幾封信（預設 10）。
    """
    service = _require_service(_GMAIL_IDX, "Gmail")
    emails = _get_recent_emails(service, query, max_results)
    if not emails:
        return "找不到符合條件的信件。"

    lines = []
    for e in emails:
        lines.append(
            f"• ID: {e['id']} | 寄件人: {e['sender']}\n"
            f"  主旨: {e['subject']}\n"
            f"  摘要: {e['snippet'][:100]}...\n"
            f"  連結: {e['url']}"
        )
    return "\n\n".join(lines)


def create_email_draft(
    to_email: str,
    subject: str,
    body_text: str,
    thread_id: str = None,
) -> str:
    """
    在 Gmail 中建立一封草稿（Draft）。

    Args:
        to_email: 收件人 Email。
        subject: 信件主旨。
        body_text: 信件內文（純文字）。
        thread_id: 若是回覆現有信件，請提供討論串 ID (threadId)。
    """
    service = _require_service(_GMAIL_IDX, "Gmail")
    draft = _create_gmail_draft(service, to_email, subject, body_text, thread_id)
    if not draft:
        raise RuntimeError("建立 Gmail 草稿失敗（API 回傳空結果）")
    return f"✅ 草稿已建立！草稿 ID: {draft['id']}"
