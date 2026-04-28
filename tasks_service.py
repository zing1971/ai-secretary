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

def list_tasks(service) -> list[dict]:
    """列出目前的待辦任務清單（含 ID，不含已完成）。"""
    results = service.tasks().list(tasklist='@default', showCompleted=False).execute()
    return [
        {
            'id': item.get('id', ''),
            'title': item.get('title', ''),
            'notes': item.get('notes', ''),
            'due': item.get('due', ''),
            'status': item.get('status', 'needsAction'),
        }
        for item in results.get('items', [])
    ]


def complete_task(service, task_id: str) -> dict:
    """將指定任務標記為已完成。"""
    try:
        return service.tasks().patch(
            tasklist='@default',
            task=task_id,
            body={'status': 'completed'},
        ).execute()
    except Exception as exc:
        raise RuntimeError(f"標記任務完成失敗 (task_id={task_id})：{exc}") from exc
