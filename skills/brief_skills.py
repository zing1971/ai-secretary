"""
晨報技能：組合今日行程、待辦事項與未讀信件。
"""

import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))

from datetime import date

from _skill_base import _GMAIL_IDX, _require_service
from gmail_service import get_recent_emails
from calendar_skills import get_todays_calendar_events
from tasks_skills import list_google_tasks


def get_morning_brief() -> str:
    """
    產生今日晨報：整合行事曆、待辦清單與未讀信件概覽。
    """
    today = date.today().strftime("%Y-%m-%d")

    cal = get_todays_calendar_events()
    tasks = list_google_tasks()

    service = _require_service(_GMAIL_IDX, "Gmail")
    emails = get_recent_emails(service, "is:unread", max_results=5)

    if emails:
        email_lines = [
            f"  • [{e['sender'][:25]}] {e['subject'][:45]}"
            for e in emails
        ]
        email_section = f"📧 未讀信件（{len(emails)} 封）\n" + "\n".join(email_lines)
    else:
        email_section = "📧 未讀信件：無"

    return (
        f"🌅 今日晨報（{today}）\n\n"
        f"📅 今日行程\n{cal}\n\n"
        f"✅ 待辦事項\n{tasks}\n\n"
        f"{email_section}"
    )
