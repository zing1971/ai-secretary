"""
自動起草回覆技能：讀取信件內容，使用 Gemini 起草專業回覆草稿。
"""

import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))

from _skill_base import _GMAIL_IDX, _require_service
from gmail_service import get_email, create_gmail_draft
from generation_skills import draft_professional_content


def draft_reply(email_id: str, hint: str = None) -> str:
    """
    讀取指定信件，由 Gemini 起草回覆並存為草稿。

    Args:
        email_id: Gmail 信件 ID（必填）。
        hint: 回覆要點提示，例如「婉拒邀約，語氣客氣」（可選）。
    """
    service = _require_service(_GMAIL_IDX, "Gmail")
    msg = get_email(service, email_id)

    if not msg:
        raise RuntimeError(f"找不到信件 (id={email_id})")

    task = "起草一封專業的電子郵件回覆"
    if hint:
        task += f"，回覆要點：{hint}"

    context = (
        f"寄件人：{msg['from']}\n"
        f"主旨：{msg['subject']}\n"
        f"日期：{msg['date']}\n\n"
        f"原始信件內容：\n{msg['body']}"
    )

    reply_body = draft_professional_content(task, context)

    subject = msg["subject"]
    if not subject.lower().startswith("re:"):
        subject = f"Re: {subject}"

    draft = create_gmail_draft(
        service,
        to_email=msg["from"],
        subject=subject,
        body_text=reply_body,
        thread_id=msg["threadId"],
    )

    if not draft:
        raise RuntimeError("建立草稿失敗")

    draft_id = draft.get("id", "")
    return (
        f"✅ 草稿已建立\n"
        f"草稿 ID：{draft_id}\n"
        f"收件人：{msg['from']}\n"
        f"主旨：{subject}\n\n"
        f"--- 草稿內文 ---\n{reply_body}"
    )
