"""
共用基礎模組：Google 服務索引常數與 _require_service() helper。
此模組由各 skill 檔案匯入，不對外暴露任何工具函數。
"""

from google_auth import get_google_services

# ── 服務索引（對應 get_google_services() 回傳的 tuple）────
_GMAIL_IDX = 0
_CALENDAR_IDX = 1
_TASKS_IDX = 2
# index 3 = sheets_service（保留）
_DRIVE_IDX = 4
_PEOPLE_IDX = 5


def _require_service(index: int, name: str) -> object:
    """
    取得指定索引的 Google 服務物件。
    若服務不可用（授權失敗），拋出 RuntimeError 讓 Hermes 正確顯示錯誤。
    """
    services = get_google_services()
    service = services[index]
    if service is None:
        raise RuntimeError(
            f"無法連線至 {name}（Google OAuth 授權失敗，"
            f"請確認 token.json 有效且已授予正確的 scope）"
        )
    return service
