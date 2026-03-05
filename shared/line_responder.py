"""
共用 LINE 回覆工具

提供統一的回覆邏輯，供 Alice 和 Birdie 共同使用。
"""
import logging

logger = logging.getLogger(__name__)


def send_response(line_service, user_id: str, reply_token: str, text: str):
    """核心回覆邏輯：優先使用 reply_token，失敗則使用 push_text"""
    if reply_token:
        success = line_service.reply_text(reply_token, text)
        if success:
            return
    line_service.push_text(text, to_user_id=user_id)
