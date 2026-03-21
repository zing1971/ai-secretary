"""
共用訊息回覆工具（平台無關版）

提供統一的回覆邏輯，供 Alice 和 Birdie 共同使用。
支援 TelegramService 與 LineService（相容介面）。
"""
import logging

logger = logging.getLogger(__name__)


def send_response(messaging_service, user_id: str, reply_token: str, text: str):
    """
    核心回覆邏輯：
    - Telegram：reply_token 即為 chat_id，直接呼叫 reply_text
    - Line（舊版）：優先使用 reply_token，失敗則改用 push_text
    """
    if reply_token:
        success = messaging_service.reply_text(reply_token, text)
        if success:
            return
    messaging_service.push_text(text, to_user_id=user_id)
