from linebot import LineBotApi, WebhookHandler
from linebot.models import TextSendMessage
from config import Config, logger


class LineService:
    def __init__(self):
        self.api = LineBotApi(Config.LINE_CHANNEL_ACCESS_TOKEN)
        self.handler = WebhookHandler(Config.LINE_CHANNEL_SECRET)
        self.user_id = Config.LINE_USER_ID

    def push_text(self, text, to_user_id=None):
        """主動推送純文字訊息"""
        target = to_user_id or self.user_id
        try:
            self.api.push_message(target, TextSendMessage(text=text))
            logger.info(f"成功推送訊息至 {target}")
            return True
        except Exception as e:
            logger.error(f"推送訊息失敗: {e}")
            return False

    def reply_text(self, reply_token, text):
        """回覆訊息"""
        try:
            self.api.reply_message(reply_token, TextSendMessage(text=text))
            return True
        except Exception as e:
            logger.error(f"回覆訊息失敗: {e}")
            return False

    def get_message_content(self, message_id: str) -> bytes:
        """取得 LINE 訊息的二進位內容（例如圖片）"""
        try:
            message_content = self.api.get_message_content(message_id)
            chunks = []
            for chunk in message_content.iter_content():
                chunks.append(chunk)
            return b''.join(chunks)
        except Exception as e:
            logger.error(f"取得訊息內容失敗: {e}")
            return None

# ⚠️ 不再在模組層級建立實例，改由 app.py 控制
