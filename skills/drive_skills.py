"""
Google Drive 技能：根據關鍵字搜尋檔案。
"""

from _skill_base import _DRIVE_IDX, _require_service
from drive_service import DriveService


def search_drive_files(keyword: str, max_results: int = 5) -> str:
    """
    根據關鍵字搜尋 Google Drive 中的檔案（包含檔名與內文）。

    Args:
        keyword: 搜尋關鍵字（必填）。
        max_results: 最多回傳幾筆結果（預設 5）。
    """
    service = _require_service(_DRIVE_IDX, "Google Drive")
    ds = DriveService(service)
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
