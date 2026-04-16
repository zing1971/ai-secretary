"""
Google Calendar 技能：查詢今日行程、建立新行程。
"""

from _skill_base import _CALENDAR_IDX, _require_service
from calendar_service import create_event as _create_event
from calendar_service import get_todays_events as _get_todays_events


def get_todays_calendar_events() -> str:
    """
    取得今日全天的行事曆行程，格式化為字串回傳。
    回傳的每一列是一個行程，包含時間、標題、地點與連結。
    """
    service = _require_service(_CALENDAR_IDX, "Google Calendar")
    events = _get_todays_events(service)
    if not events:
        return "今天沒有任何行程。"
    return "\n".join(events)


def create_calendar_event(
    title: str,
    start_time: str,
    end_time: str,
    description: str = None,
    location: str = None,
) -> str:
    """
    在 Google Calendar 建立一個新行程。

    Args:
        title: 行程標題（必填）。
        start_time: 開始時間。格式為 "YYYY-MM-DD HH:MM"（台北時間）
                    或 "YYYY-MM-DD"（全天行程）。
        end_time: 結束時間，格式同上。
        description: 備註說明（可選）。
        location: 地點（可選）。

    範例：
        create_calendar_event("週會", "2026-04-20 10:00", "2026-04-20 11:00", location="會議室 A")
        create_calendar_event("休假", "2026-04-25", "2026-04-26")
    """
    service = _require_service(_CALENDAR_IDX, "Google Calendar")
    result = _create_event(service, title, start_time, end_time, description, location)
    if not result:
        raise RuntimeError(f"建立行事曆行程失敗（title={title!r}）")
    html_link = result.get("htmlLink", "")
    link_str = f"\n🔗 {html_link}" if html_link else ""
    return f"✅ 已建立行程：{title}\n  開始：{start_time} | 結束：{end_time}{link_str}"
