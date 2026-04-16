"""
Google Tasks 技能：新增待辦任務、列出任務清單。
"""

from _skill_base import _TASKS_IDX, _require_service
from tasks_service import create_google_task as _create_task
from tasks_service import list_tasks as _list_tasks


def add_google_task(
    title: str,
    notes: str = None,
    due: str = None,
) -> str:
    """
    建立一項新的 Google Tasks 待辦任務。

    Args:
        title: 任務標題（必填）。
        notes: 任務備註 / 詳細說明（可選）。
        due: 到期日，RFC3339 格式，例如 "2026-03-01T23:59:59Z"（可選）。
    """
    service = _require_service(_TASKS_IDX, "Google Tasks")
    result = _create_task(service, title, notes, due)
    if not result:
        raise RuntimeError(f"建立 Google Tasks 任務失敗（title={title!r}）")
    return f"✅ 已建立任務：{title}"


def list_google_tasks() -> str:
    """
    列出預設清單中的所有 Google Tasks 待辦任務。
    """
    service = _require_service(_TASKS_IDX, "Google Tasks")
    tasks = _list_tasks(service)
    if not tasks:
        return "目前沒有任何待辦任務。"
    return "\n".join(tasks)
