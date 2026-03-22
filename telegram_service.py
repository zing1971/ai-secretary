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
                    {"text": "📅 行程安排", "callback_data": "未來兩天行程"},
                ],
                [
                    {"text": "✅ 待辦事項", "callback_data": "列出待辦事項"},
                    {"text": "📧 郵件中心", "callback_data": "進入郵件處理中心"},
                ],
                [
                    {"text": "📚 知識搜尋", "callback_data": "開啟專業知識庫"},
                    {"text": "⚙️ 系統設定", "callback_data": "查看個人偏好與設定"},
                ],
                [
                    {"text": "👥 整理聯絡人", "callback_data": "幫聯絡人貼標籤"},
                    {"text": "☁️ 整理雲端", "callback_data": "整理雲端"},
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

    def send_email_menu(self, chat_id: str = None) -> bool:
        """傳送郵件中心功能選單"""
        target = chat_id or self.chat_id
        keyboard = {
            "inline_keyboard": [
                [
                    {"text": "📊 摘要重要信件", "callback_data": "幫我挑三到五封重要信件摘要"},
                    {"text": "🔍 搜尋特定信件", "callback_data": "我要找信件"}
                ],
                [
                    {"text": "✏️ 我想草擬回信", "callback_data": "幫我草擬回信"},
                    {"text": "🔙 返回主選單", "callback_data": "menu"}
                ]
            ]
        }
        return self._send_message(target, "📧 【郵件中心】\n仁哥，請問您想如何處理電子郵件？", reply_markup=keyboard)

    def send_knowledge_menu(self, chat_id: str = None) -> bool:
        """傳送知識庫導引選單"""
        target = chat_id or self.chat_id
        keyboard = {
            "inline_keyboard": [
                [
                    {"text": "🛡️ 資安防護", "callback_data": "資安專業知識查詢"},
                    {"text": "💻 資訊技術", "callback_data": "IT技術架構查詢"}
                ],
                [
                    {"text": "📈 科技趨勢", "callback_data": "最新科技趨勢分析"},
                    {"text": "🌐 外部搜尋", "callback_data": "上網搜尋相關資訊"}
                ]
            ]
        }
        return self._send_message(target, "📚 【專業知識庫】\n仁哥，請問您想查詢哪個領域的知識？或是需要 Alice 上網幫您查證最新的國內外情資呢？", reply_markup=keyboard)

    def send_settings_menu(self, memories_summary: str, chat_id: str = None) -> bool:
        """傳送系統與偏好設定選單"""
        target = chat_id or self.chat_id
        keyboard = {
            "inline_keyboard": [
                [
                    {"text": "📝 新增個人備忘", "callback_data": "記住我的新偏好"},
                    {"text": "🔄 重寫偏好摘要", "callback_data": "總結目前我記住的事情"}
                ],
                [
                    {"text": "🔙 返回主選單", "callback_data": "menu"}
                ]
            ]
        }
        text = f"⚙️ 【系統設定與個人化記憶】\n目前 Alice 腦袋裡的「仁哥檔案」：\n\n{memories_summary}\n\n請問需要協助更新或調整哪一部分嗎？"
        return self._send_message(target, text, reply_markup=keyboard)

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
