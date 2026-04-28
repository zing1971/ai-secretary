"""
Gmail 技能：搜尋、讀取、起草、發送、回覆信件。
"""

import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))

from _skill_base import _GMAIL_IDX, _require_service
from gmail_service import create_gmail_draft as _create_gmail_draft
from gmail_service import get_recent_emails as _get_recent_emails
from gmail_service import get_email as _get_email
from gmail_service import send_draft as _send_draft
from gmail_service import send_reply as _send_reply


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
            f"• ID: {e['id']} | Thread: {e['threadId']}\n"
            f"  寄件人: {e['sender']}\n"
            f"  主旨: {e['subject']}\n"
            f"  摘要: {e['snippet'][:100]}...\n"
            f"  連結: {e['url']}"
        )
    return "\n\n".join(lines)


def read_email(msg_id: str) -> str:
    """
    讀取單封信件的完整內容。

    Args:
        msg_id: 信件 ID（從 search 結果取得）。
    """
    service = _require_service(_GMAIL_IDX, "Gmail")
    email = _get_email(service, msg_id)
    if not email:
        raise RuntimeError(f"找不到信件（msg_id={msg_id!r}）")
    due_str = f"\n  日期: {email['date']}" if email['date'] else ""
    return (
        f"📧 信件詳情\n"
        f"  ID: {email['id']} | Thread: {email['threadId']}\n"
        f"  寄件人: {email['from']}\n"
        f"  收件人: {email['to']}\n"
        f"  主旨: {email['subject']}{due_str}\n"
        f"  連結: {email['url']}\n\n"
        f"--- 內文 ---\n{email['body']}"
    )


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


def send_email_draft(draft_id: str) -> str:
    """
    發送已存在的 Gmail 草稿。

    Args:
        draft_id: 草稿 ID（從 draft 建立結果取得）。
    """
    service = _require_service(_GMAIL_IDX, "Gmail")
    result = _send_draft(service, draft_id)
    if not result:
        raise RuntimeError(f"發送草稿失敗（draft_id={draft_id!r}）")
    return f"✅ 信件已發送！Message ID: {result.get('id', '')}"


def reply_to_email(
    thread_id: str,
    to_email: str,
    subject: str,
    body_text: str,
) -> str:
    """
    直接回覆信件（發送，不存草稿）。

    Args:
        thread_id: 討論串 ID（從 search 或 read 結果取得）。
        to_email: 收件人 Email。
        subject: 回覆主旨（若未以 Re: 開頭，自動加上）。
        body_text: 回覆內文。
    """
    service = _require_service(_GMAIL_IDX, "Gmail")
    result = _send_reply(service, thread_id, to_email, subject, body_text)
    if not result:
        raise RuntimeError(f"發送回覆失敗（thread_id={thread_id!r}）")
    return f"✅ 回覆已發送！Message ID: {result.get('id', '')}"
