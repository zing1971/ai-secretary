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
        傳送純文字主選單提示 (配合 Hermes 對話介面)
        """
        target = chat_id or self.chat_id
        text = (
            "📋 **AI 秘書主選單**\n\n"
            "您可以隨時對我說以下指令：\n"
            "• 「今天摘要」：查看今日總覽\n"
            "• 「未來兩天行程」：查看行程安排\n"
            "• 「列出待辦事項」：查看待辦清單\n"
            "• 「進入郵件處理中心」：處理電子郵件\n"
            "• 「開啟專業知識庫」：搜尋或提問專業知識\n"
            "• 「查看個人偏好與設定」：管理系統設定\n"
            "• 「幫聯絡人貼標籤」或「整理雲端」"
        )
        return self._send_message(target, text, parse_mode="Markdown")

    def send_context_menu(self, context_type: str, chat_id: str = None) -> bool:
        """傳送特定情境的純文字選單"""
        target = chat_id or self.chat_id
        text = ""

        if context_type == "morning_briefing":
            text = (
                "💡 **後續動作建議**\n"
                "您可以對我說：\n"
                "• 「幫我起草今天重要信件的回覆」\n"
                "• 「把簡報中的重點加入待辦清單」"
            )

        if text:
            return self._send_message(target, text, parse_mode="Markdown")
        return False

    def send_email_menu(self, chat_id: str = None) -> bool:
        """傳送郵件中心功能選單 (純文字)"""
        target = chat_id or self.chat_id
        text = (
            "📧 **【郵件中心】**\n"
            "仁哥，請問您想如何處理電子郵件？您可以對我說：\n"
            "• 「幫我挑三到五封重要信件摘要」\n"
            "• 「我要找信件...」\n"
            "• 「幫我草擬回信...」\n"
            "• 「返回主選單」"
        )
        return self._send_message(target, text, parse_mode="Markdown")

    def send_knowledge_menu(self, chat_id: str = None) -> bool:
        """傳送知識庫導引選單 (純文字)"""
        target = chat_id or self.chat_id
        text = (
            "📚 **【專業知識庫】**\n"
            "仁哥，請問您想查詢哪個領域的知識？或是需要 Alice 上網幫您查證最新的國內外情資呢？\n"
            "您可以說：\n"
            "• 「查詢資安專業知識...」\n"
            "• 「查詢 IT 技術架構...」\n"
            "• 「分析最新科技趨勢...」\n"
            "• 「幫我上網搜尋...」"
        )
        return self._send_message(target, text, parse_mode="Markdown")

    def send_settings_menu(self, memories_summary: str, chat_id: str = None) -> bool:
        """傳送系統與偏好設定選單 (純文字)"""
        target = chat_id or self.chat_id
        text = (
            f"⚙️ **【系統設定與個人化記憶】**\n"
            f"目前 Alice 腦袋裡的「仁哥檔案」：\n\n"
            f"{memories_summary}\n\n"
            f"請問需要協助更新或調整哪一部分嗎？您可以對我說：\n"
            f"• 「記住我的新偏好...」\n"
            f"• 「總結目前我記住的事情」\n"
            f"• 「返回主選單」"
        )
        return self._send_message(target, text, parse_mode="Markdown")

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
