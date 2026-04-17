"""
跨 session 長期記憶技能。
記憶以 JSON 存儲於 ~/.hermes/alice_memory.json，服務重啟後仍保留。
main.py 啟動時會自動將記憶注入 SOUL.md，讓 AI 在每個 session 都知道歷史脈絡。
"""

import json
import os
from datetime import datetime

_MEMORY_PATH = os.path.expanduser("~/.hermes/alice_memory.json")


def _load() -> dict:
    """載入記憶 JSON，讀取失敗時回傳空 dict。"""
    if not os.path.exists(_MEMORY_PATH):
        return {}
    try:
        with open(_MEMORY_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _save(memory: dict) -> None:
    """將記憶寫入 JSON 檔案。"""
    os.makedirs(os.path.dirname(_MEMORY_PATH), exist_ok=True)
    with open(_MEMORY_PATH, "w", encoding="utf-8") as f:
        json.dump(memory, f, ensure_ascii=False, indent=2)


def remember(topic: str, content: str) -> str:
    """
    將重要資訊存入長期記憶，跨 session 永久保留。
    同一主題再次記憶會覆蓋舊內容。

    Args:
        topic: 記憶主題（簡短標籤），例如「仁哥偏好報告格式」、「王大明手機」。
        content: 要記憶的內容，建議具體且完整。

    範例：
        remember("仁哥行事曆偏好", "週一到週五 9-18 點工作，午休 12-13 點不排會議")
        remember("艾哲森董事長聯絡資訊", "Email: allen@xxx.com，助理: 林小姐 02-2345-6789")
    """
    memory = _load()
    memory[topic] = {
        "content": content,
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }
    _save(memory)
    return f"✅ 已記住：**{topic}**\n  內容：{content}"


def recall(query: str = None) -> str:
    """
    查詢長期記憶。不指定關鍵字則列出全部記憶。

    Args:
        query: 搜尋關鍵字（可選）。可用主題名稱或內容片段搜尋。
               例如 "董事長"、"偏好"、"手機"。
    """
    memory = _load()
    if not memory:
        return "目前沒有任何長期記憶。"

    if query:
        q = query.lower()
        matched = {
            k: v for k, v in memory.items()
            if q in k.lower() or q in v["content"].lower()
        }
        if not matched:
            return f"找不到包含「{query}」的記憶。"
        memory = matched

    lines = [f"**長期記憶**（共 {len(memory)} 條）\n"]
    for topic, data in memory.items():
        lines.append(
            f"• **{topic}**：{data['content']}\n"
            f"  _（更新：{data['updated_at']}）_"
        )
    return "\n".join(lines)


def forget(topic: str) -> str:
    """
    刪除指定主題的長期記憶。

    Args:
        topic: 要刪除的記憶主題，需與 remember 時的 topic 完全一致。
               可先用 recall() 確認正確主題名稱。
    """
    memory = _load()
    if topic not in memory:
        return f"找不到主題為「{topic}」的記憶，請用 recall() 確認主題名稱。"
    del memory[topic]
    _save(memory)
    return f"🗑️ 已刪除記憶：**{topic}**"
