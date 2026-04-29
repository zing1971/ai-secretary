"""
共用基礎模組：Google 服務索引常數與 _require_service() helper。
此模組由各 skill 檔案匯入，不對外暴露任何工具函數。
"""

import logging
import threading

from google_auth import get_google_services

logger = logging.getLogger(__name__)

# ── 服務索引（對應 get_google_services() 回傳的 tuple）────
_GMAIL_IDX = 0
_CALENDAR_IDX = 1
_TASKS_IDX = 2
_SHEETS_IDX = 3
_DRIVE_IDX = 4
_PEOPLE_IDX = 5

# ── 模組層級服務快取（避免每次 skill 呼叫都重走 OAuth 流程）────
_services_cache: tuple | None = None
_services_lock = threading.Lock()


def _get_services() -> tuple:
    """
    取得並快取 Google 服務 tuple。
    首次呼叫時執行 OAuth 流程，後續直接回傳快取。
    若 token 失效（服務物件為 None），自動清除快取並重建。
    使用 threading.Lock 防止並發請求競爭刷新 token。
    """
    global _services_cache
    with _services_lock:
        if _services_cache is not None:
            return _services_cache
        logger.debug("建立 Google 服務連線...")
        _services_cache = get_google_services()
        return _services_cache


def invalidate_services_cache() -> None:
    """強制清除服務快取，下次呼叫將重新執行 OAuth 流程。"""
    global _services_cache
    with _services_lock:
        _services_cache = None
        logger.info("Google 服務快取已清除，下次呼叫將重新認證。")


def _require_service(index: int, name: str) -> object:
    """
    取得指定索引的 Google 服務物件。
    若服務不可用（授權失敗），清除快取後拋出 RuntimeError
    讓 Hermes 正確顯示錯誤。
    """
    services = _get_services()
    service = services[index]
    if service is None:
        # 清除快取，避免後續呼叫繼續使用失效的服務
        invalidate_services_cache()
        raise RuntimeError(
            f"無法連線至 {name}（Google OAuth 授權失敗，"
            f"請確認 token.json 有效且已授予正確的 scope）"
        )
    return service
