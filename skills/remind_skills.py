"""
提醒技能：快速建立帶時間的行事曆提醒事項。
"""

import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))

from datetime import datetime, timedelta

from calendar_skills import create_calendar_event


def set_reminder(at: str, msg: str) -> str:
    """
    在指定時間建立 15 分鐘的行事曆提醒事項。

    Args:
        at: 提醒時間，格式 "YYYY-MM-DD HH:MM"（必填）。
        msg: 提醒內容（必填）。
    """
    try:
        dt = datetime.strptime(at.strip(), "%Y-%m-%d %H:%M")
    except ValueError:
        raise RuntimeError(
            f"時間格式錯誤，請用 'YYYY-MM-DD HH:MM'，收到：{at!r}"
        )

    end_str = (dt + timedelta(minutes=15)).strftime("%Y-%m-%d %H:%M")
    return create_calendar_event(
        title=f"⏰ {msg}",
        start=at,
        end=end_str,
    )
