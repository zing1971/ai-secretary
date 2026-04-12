"""
Google Workspace 技能封裝模組，供 Hermes Agent 取用。
這些函數會自動取得 Google 授權，並調用背後的 service 層進行操作。
"""

from google_auth import get_google_services
from gmail_service import get_recent_emails as _get_recent_emails, create_gmail_draft as _create_gmail_draft
from calendar_service import get_events, get_todays_events as _get_todays_events
from tasks_service import create_google_task as _create_task, list_tasks as _list_tasks
from drive_service import DriveService

def get_todays_calendar_events() -> str:
    """
    取得今日全天的行事曆行程，並格式化為字串回傳。
    回傳的每一列是一個行程包含時間、標題、地點與網址。
    """
    _, calendar_service, _, _, _, _ = get_google_services()
    if not calendar_service:
        return "無法連線至 Google Calendar (授權失敗)"
    
    events = _get_todays_events(calendar_service)
    if not events:
        return "今天沒有任何行程。"
    return "\n".join(events)

def search_recent_gmails(query: str = None, max_results: int = 10) -> str:
    """
    搜尋並取得近期的 Gmail 信件。
    
    Args:
        query: Gmail 搜尋語法，例如 "is:unread" 或 "from:boss@example.com"。若不提供預設尋找近3天未讀。
        max_results: 最多回傳幾封信。
    """
    gmail_service, _, _, _, _, _ = get_google_services()
    if not gmail_service:
        return "無法連線至 Gmail (授權失敗)"
    
    emails = _get_recent_emails(gmail_service, query, max_results)
    if not emails:
        return "找不到符合條件的信件。"
    
    result_lines = []
    for e in emails:
        result_lines.append(f"• ID: {e['id']} | 寄件人: {e['sender']}\n"
                            f"  主旨: {e['subject']}\n"
                            f"  摘要: {e['snippet'][:100]}...\n"
                            f"  連結: {e['url']}")
    return "\n\n".join(result_lines)

def create_email_draft(to_email: str, subject: str, body_text: str, thread_id: str = None) -> str:
    """
    在 Gmail 中建立一封回覆草稿 (Draft)。

    Args:
        to_email: 收件人 Email。
        subject: 信件主旨。
        body_text: 信件內文。
        thread_id: 若是回覆現有信件，請提供信件討論串 ID (threadId)。
    """
    gmail_service, _, _, _, _, _ = get_google_services()
    if not gmail_service:
        return "無法連線至 Gmail (授權失敗)"
    
    draft = _create_gmail_draft(gmail_service, to_email, subject, body_text, thread_id)
    if draft:
        return f"✅ 草稿已建立！草稿 ID: {draft['id']}"
    return "建立草稿失敗。"



def add_google_task(title: str, notes: str = None, due: str = None) -> str:
    """
    建立一項新的 Google Tasks 任務。
    
    Args:
        title: 任務標題
        notes: 任務詳細內容 / 備註
        due: 到期日 (RFC3339 格式字串, 如 '2026-03-01T23:59:59Z')
    """
    _, _, tasks_service, _, _, _ = get_google_services()
    if not tasks_service:
        return "無法連線至 Google Tasks (授權失敗)"
    
    res = _create_task(tasks_service, title, notes, due)
    if res:
        return f"✅ 已建立任務: {title}"
    return "建立任務失敗。"

def list_google_tasks() -> str:
    """
    列出目標清單（預設清單）中的目前 Google Tasks 任務。
    """
    _, _, tasks_service, _, _, _ = get_google_services()
    if not tasks_service:
        return "無法連線至 Google Tasks (授權失敗)"
    
    tasks = _list_tasks(tasks_service)
    if not tasks:
        return "目前沒有任何待辦任務。"
    return "\n".join(tasks)

def search_drive_files(keyword: str, max_results: int = 5) -> str:
    """
    根據關鍵字搜尋 Google Drive 中的檔案（包含檔名與內文）。
    
    Args:
        keyword: 搜尋關鍵字
        max_results: 最多回傳幾筆結果，預設為 5
    """
    _, _, _, _, drive_service, _ = get_google_services()
    if not drive_service:
        return "無法連線至 Google Drive (授權失敗)"
    
    ds = DriveService(drive_service)
    files = ds.search_files_by_keyword(keyword, max_results)
    
    if not files:
        return f"找不到包含「{keyword}」的檔案。"
    
    result_lines = []
    for f in files:
        result_lines.append(f"• 品名/檔名: {f.get('name')} | 類型: {f.get('mimeType')}\n"
                            f"  連結: {f.get('webViewLink')}")
    return "\n\n".join(result_lines)

