"""
Google Workspace 技能封裝模組，供 Hermes Agent 取用。
這些函數會自動取得 Google 授權，並調用背後的 service 層進行操作。
授權失敗或操作異常時拋出 RuntimeError，讓 Hermes 能正確顯示錯誤。
"""

from google_auth import get_google_services
from gmail_service import get_recent_emails as _get_recent_emails
from gmail_service import create_gmail_draft as _create_gmail_draft
from calendar_service import get_todays_events as _get_todays_events
from tasks_service import create_google_task as _create_task
from tasks_service import list_tasks as _list_tasks
from drive_service import DriveService

# ── 服務索引常數 ────────────────────────────────────────────
_GMAIL_IDX = 0
_CALENDAR_IDX = 1
_TASKS_IDX = 2
_DRIVE_IDX = 4


def _require_service(index: int, name: str) -> object:
    """
    取得指定索引的 Google 服務物件。
    若服務不可用（授權失敗），拋出 RuntimeError 讓 Hermes 正確處理錯誤。
    """
    services = get_google_services()
    service = services[index]
    if service is None:
        raise RuntimeError(
            f"無法連線至 {name}（Google OAuth 授權失敗，"
            f"請確認 token.json 有效且已授予正確的 scope）"
        )
    return service


from functools import wraps

def safe_tool(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            return f"❌ 技能執行失敗：{str(e)}。請提醒使用者檢查授權或系統設定。"
    return wrapper

# ── 技能函數 ────────────────────────────────────────────────


@safe_tool
def get_todays_calendar_events() -> str:
    """
    取得今日全天的行事曆行程，並格式化為字串回傳。
    回傳的每一列是一個行程，包含時間、標題、地點與連結。
    """
    calendar_service = _require_service(_CALENDAR_IDX, "Google Calendar")
    events = _get_todays_events(calendar_service)
    if not events:
        return "今天沒有任何行程。"
    return "\n".join(events)


@safe_tool
def search_recent_gmails(query: str = None, max_results: int = 10) -> str:
    """
    搜尋並取得近期的 Gmail 信件。

    Args:
        query: Gmail 搜尋語法，例如 "is:unread" 或 "from:boss@example.com"。
               若不提供，預設搜尋近 3 天未讀信件。
        max_results: 最多回傳幾封信（預設 10）。
    """
    gmail_service = _require_service(_GMAIL_IDX, "Gmail")
    emails = _get_recent_emails(gmail_service, query, max_results)
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


@safe_tool
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
    gmail_service = _require_service(_GMAIL_IDX, "Gmail")
    draft = _create_gmail_draft(gmail_service, to_email, subject, body_text, thread_id)
    if not draft:
        raise RuntimeError("建立 Gmail 草稿失敗（API 回傳空結果）")
    return f"✅ 草稿已建立！草稿 ID: {draft['id']}"


@safe_tool
def add_google_task(
    title: str,
    notes: str = None,
    due: str = None,
) -> str:
    """
    建立一項新的 Google Tasks 任務。

    Args:
        title: 任務標題。
        notes: 任務備註 / 詳細說明。
        due: 到期日（RFC3339 格式，例如 '2026-03-01T23:59:59Z'）。
    """
    tasks_service = _require_service(_TASKS_IDX, "Google Tasks")
    result = _create_task(tasks_service, title, notes, due)
    if not result:
        raise RuntimeError(f"建立 Google Tasks 任務失敗（title={title!r}）")
    return f"✅ 已建立任務：{title}"


@safe_tool
def list_google_tasks() -> str:
    """
    列出預設清單中的所有 Google Tasks 待辦任務。
    """
    tasks_service = _require_service(_TASKS_IDX, "Google Tasks")
    tasks = _list_tasks(tasks_service)
    if not tasks:
        return "目前沒有任何待辦任務。"
    return "\n".join(tasks)


@safe_tool
def search_drive_files(keyword: str, max_results: int = 5) -> str:
    """
    根據關鍵字搜尋 Google Drive 中的檔案（包含檔名與內文）。

    Args:
        keyword: 搜尋關鍵字。
        max_results: 最多回傳幾筆結果（預設 5）。
    """
    drive_service = _require_service(_DRIVE_IDX, "Google Drive")
    ds = DriveService(drive_service)
    files = ds.search_files_by_keyword(keyword, max_results)
    if not files:
        return f"找不到包含「{keyword}」的檔案。"

    lines = []
    for f in files:
        lines.append(
            f"• 檔名: {f.get('name')} | 類型: {f.get('mimeType')}\n"
            f"  連結: {f.get('webViewLink')}"
        )
    return "\n\n".join(lines)
