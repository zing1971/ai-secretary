"""
Google Calendar 技能：查詢今日行程、查詢日期範圍行程、建立、更新、刪除行程。
"""

import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))

from _skill_base import _CALENDAR_IDX, _require_service
from calendar_service import create_event as _create_event
from calendar_service import get_todays_events as _get_todays_events
from calendar_service import get_events_range as _get_events_range
from calendar_service import update_event as _update_event
from calendar_service import delete_event as _delete_event


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


def get_calendar_events_range(from_date: str, to_date: str) -> str:
    """
    取得指定日期範圍內的行事曆行程。

    Args:
        from_date: 開始日期，格式 "YYYY-MM-DD"。
        to_date: 結束日期，格式 "YYYY-MM-DD"（含當天到 23:59）。
    """
    service = _require_service(_CALENDAR_IDX, "Google Calendar")
    events = _get_events_range(service, from_date, to_date)
    if not events:
        return f"在 {from_date} ~ {to_date} 期間沒有任何行程。"
    return "\n".join(events)


def update_calendar_event(
    event_id: str,
    title: str = None,
    start_time: str = None,
    end_time: str = None,
    description: str = None,
    location: str = None,
) -> str:
    """
    更新已存在的 Google Calendar 行程（只修改提供的欄位）。

    Args:
        event_id: 行程 ID（從 Calendar API 取得）。
        title: 新標題（可選）。
        start_time: 新開始時間，格式 "YYYY-MM-DD HH:MM" 或 "YYYY-MM-DD"（可選）。
        end_time: 新結束時間，格式同上（可選）。
        description: 新備註（可選）。
        location: 新地點（可選）。
    """
    service = _require_service(_CALENDAR_IDX, "Google Calendar")
    result = _update_event(service, event_id, title, start_time, end_time, description, location)
    return f"✅ 行程已更新！Event ID: {result.get('id', event_id)}"


def delete_calendar_event(event_id: str) -> str:
    """
    刪除指定的 Google Calendar 行程。

    Args:
        event_id: 行程 ID。
    """
    service = _require_service(_CALENDAR_IDX, "Google Calendar")
    _delete_event(service, event_id)
    return f"✅ 行程已刪除（event_id={event_id}）"
