import datetime

def create_google_task(service, title, notes=None, due=None):
    """
    建立一項新的 Google Tasks 任務。
    
    :param service: Google Tasks API service 實例
    :param title: 任務標題
    :param notes: 任務詳細內容 / 備註
    :param due: 到期日 (字串格式, 如 '2026-03-01T23:59:59Z')
    """
    task = {
        'title': title,
        'notes': notes
    }
    if due:
        task['due'] = due

    result = service.tasks().insert(tasklist='@default', body=task).execute()
    return result

def list_tasks(service):
    """列出目前的任務清單。"""
    results = service.tasks().list(tasklist='@default').execute()
    items = results.get('items', [])
    processed_tasks = []
    for item in items:
        processed_tasks.append(f"[{item.get('title')}] - {item.get('notes', '無備註')}")
    return processed_tasks
