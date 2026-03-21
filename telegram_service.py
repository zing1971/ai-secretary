"""
Telegram Bot 服務封裝 — 取代原有的 line_service.py

提供與 LineService 相同的公開介面：
  - push_text(text, to_user_id=None)
  - reply_text(reply_token, text)   ← reply_token 在 Telegram 中對應 chat_id
  - get_message_content(message_id) ← 用於取得圖片 bytes

使用 python-telegram-bot v20+ 的同步 Bot API。
"""
import logging
import requests
from config import Config, logger


class TelegramService:
    """Telegram Bot 訊息收發核心服務"""

    BASE_URL = "https://api.telegram.org/bot{token}/{method}"

    def __init__(self):
        self.token = Config.TELEGRAM_BOT_TOKEN
        self.chat_id = Config.TELEGRAM_CHAT_ID   # 主要使用者的 chat_id
        self._base = f"https://api.telegram.org/bot{self.token}"
        logger.info(f"✅ TelegramService 初始化完成 (chat_id={self.chat_id})")

    # ── 公開介面（與 LineService 相容）──────────────────────────────────────

    @property
    def user_id(self) -> str:
        """與 LineService.user_id 相容 — 回傳主要使用者的 chat_id"""
        return self.chat_id

    def push_text(self, text: str, to_user_id: str = None, reply_markup: dict = None) -> bool:
        """主動推送純文字訊息（push message）"""
        target = to_user_id or self.chat_id
        return self._send_message(target, text, reply_markup=reply_markup)

    def reply_text(self, reply_token: str, text: str, reply_markup: dict = None) -> bool:
        """
        回覆訊息。
        Telegram 無 reply_token 機制，此處 reply_token 傳入的是 chat_id。
        呼叫端（app.py handle_message）會把 update.effective_chat.id 當 reply_token 傳入。
        """
        chat_id = reply_token or self.chat_id
        return self._send_message(chat_id, text, reply_markup=reply_markup)

    def get_message_content(self, file_id: str) -> bytes:
        """
        取得 Telegram 檔案（圖片）的二進位內容。
        file_id 對應 Telegram 的 photo[-1].file_id（最高解析度）。
        """
        try:
            # 1. 取得 file_path
            resp = requests.get(
                f"{self._base}/getFile",
                params={"file_id": file_id},
                timeout=15
            )
            resp.raise_for_status()
            file_path = resp.json()["result"]["file_path"]

            # 2. 下載檔案內容
            download_url = f"https://api.telegram.org/file/bot{self.token}/{file_path}"
            content_resp = requests.get(download_url, timeout=30)
            content_resp.raise_for_status()
            return content_resp.content

        except Exception as e:
            logger.error(f"取得 Telegram 檔案內容失敗: {e}")
            return None

    # ── Inline Keyboard 快捷選單（取代 Rich Menu）───────────────────────────

    def send_main_menu(self, chat_id: str = None) -> bool:
        """
        傳送互動式 Inline Keyboard 主選單。
        2 欄 × 3 列，共 6 個快捷按鈕。
        """
        target = chat_id or self.chat_id
        keyboard = {
            "inline_keyboard": [
                [
                    {"text": "📊 今日總覽", "callback_data": "今天摘要"},
                    {"text": "📅 行程安排", "callback_data": "查詢我未來2天的工作安排，提醒需要準備的事項"},
                ],
                [
                    {"text": "✅ 待辦事項", "callback_data": "列出所有待辦事項，依緊急程度排序"},
                    {"text": "📧 郵件處理", "callback_data": "摘要最新15封郵件重點，標註需要回覆的信"},
                ],
                [
                    {"text": "📚 知識搜尋", "callback_data": "查詢資安知識庫，整理最新威脅情報與防護建議"},
                    {"text": "⚙️ 系統設定", "callback_data": "告訴我你們目前知道關於我的所有偏好設定和重要備忘"},
                ],
                [
                    {"text": "👥 整理聯絡人", "callback_data": "整理聯絡人"},
                    {"text": "☁️ 整理雲端", "callback_data": "整理雲端，分析目錄結構並提出分類建議"},
                ],
            ]
        }
        return self._send_message(target, "📋 AI 秘書主選單", reply_markup=keyboard)

    def send_context_menu(self, context_type: str, chat_id: str = None) -> bool:
        """傳送特定情境的快捷選單"""
        target = chat_id or self.chat_id
        keyboard = None
        text = ""

        if context_type == "morning_briefing":
            keyboard = {
                "inline_keyboard": [
                    [
                        {"text": "✏️ 幫我起草重要回信", "callback_data": "幫我起草今天重要信件的回覆"},
                        {"text": "📝 記錄至待辦事項", "callback_data": "把簡報中的重點加入待辦清單"},
                    ]
                ]
            }
            text = "💡 請問需要為您執行哪些後續動作？"

        if keyboard and text:
            return self._send_message(target, text, reply_markup=keyboard)
        return False

    # ── 內部工具 ──────────────────────────────────────────────────────────────

    def _send_message(self, chat_id: str, text: str,
                      reply_markup: dict = None, parse_mode: str = None) -> bool:
        """
        呼叫 Telegram sendMessage API。
        自動切割超過 4096 字元的長訊息。
        """
        # Telegram 單則訊息上限 4096 字元
        MAX_LEN = 4096
        chunks = [text[i:i + MAX_LEN] for i in range(0, len(text), MAX_LEN)]

        success = True
        for idx, chunk in enumerate(chunks):
            payload: dict = {"chat_id": chat_id, "text": chunk}
            if parse_mode:
                payload["parse_mode"] = parse_mode
            # 只在最後一則訊息附上 keyboard
            if reply_markup and idx == len(chunks) - 1:
                payload["reply_markup"] = reply_markup

            try:
                resp = requests.post(
                    f"{self._base}/sendMessage",
                    json=payload,
                    timeout=15
                )
                if not resp.ok:
                    logger.error(f"Telegram sendMessage 失敗: {resp.text}")
                    success = False
                else:
                    logger.info(f"成功傳送訊息至 chat_id={chat_id}")
            except Exception as e:
                logger.error(f"Telegram sendMessage 例外: {e}")
                success = False

        return success
