"""
Alice — 🔍 情報秘書 查詢處理器

負責所有「唯讀」的資訊查詢動作：
- Query_Email: 信件摘要
- Query_Calendar: 行程查詢
- Search_Drive: 雲端檔案搜尋
- Query_Project_Advisor: 知識庫查詢
- Search_Web: 網際網路搜尋
- Chat: 閒聊對話
"""
import datetime
import pytz
import threading
import logging

from shared.line_responder import send_response

logger = logging.getLogger(__name__)


class AliceQueryHandler:
    """Alice 的查詢分派核心：所有查詢類意圖在此處理"""

    # Alice 負責的意圖清單
    HANDLED_INTENTS = {
        "Chat", "Query_Email", "Query_Calendar", "Search_Drive",
        "Query_Project_Advisor", "Search_Web", "Query_Tasks",
        "Visual_Assistant",
    }

    def __init__(self, messaging_service, llm_service, gmail, calendar, tasks,
                 memory_service, notebooklm_service, drive_service_wrapper=None):
        self.line = messaging_service
        self.llm = llm_service
        self.gmail = gmail
        self.calendar = calendar
        self.tasks = tasks
        self.memory = memory_service
        self.notebooklm = notebooklm_service
        self.drive = drive_service_wrapper  # DriveService (非 DriveOrganizer)
        self._handoff_fn = None  # 跨角色轉交回呼

    def set_handoff(self, handoff_fn):
        """設定跨角色轉交函數（由 RoleDispatcher 注入）"""
        self._handoff_fn = handoff_fn

    def can_handle(self, intent: str) -> bool:
        return intent in self.HANDLED_INTENTS

    def dispatch(self, intent_data, user_msg: str, user_id: str, reply_token: str = None):
        """根據意圖分派查詢動作"""
        if isinstance(intent_data, str):
            intent = intent_data
            time_range = {"start_offset": 0, "end_offset": 0, "label": "今天"}
        else:
            intent = intent_data.get("intent", "Chat")
            time_range = intent_data.get("time_range", {"start_offset": 0, "end_offset": 0, "label": "今天"})

        logger.info(f"🔍 Alice 處理查詢: {intent}")

        try:
            if intent == "Chat":
                self._handle_chat(user_msg, user_id, reply_token)

            elif intent == "Query_Email":
                self._handle_email_query(intent_data, user_msg, user_id, reply_token)

            elif intent == "Query_Calendar":
                self._handle_calendar_query(intent_data, user_msg, user_id, reply_token, time_range)

            elif intent == "Search_Drive":
                self._handle_drive_search(intent_data, user_msg, user_id, reply_token)

            elif intent == "Query_Project_Advisor":
                self._handle_knowledge_query(intent_data, user_msg, user_id, reply_token)

            elif intent == "Search_Web":
                self._handle_web_search(intent_data, user_msg, user_id, reply_token)

            elif intent == "Query_Tasks":
                self._handle_tasks_query(user_msg, user_id, reply_token)

            elif intent == "Visual_Assistant":
                self._send(user_id, reply_token,
                    "📸 好的，仁哥！\n"
                    "您可以現在傳送「名片」、「會議筆記」或「活動海報」的照片給我，"
                    "Alice 會立刻為您分析並自動建立聯絡人或行程叮嚀喔！😊")

        except Exception as e:
            logger.error(f"❌ Alice 處理查詢異常: {e}")
            self._send(user_id, reply_token,
                f"仁哥抱歉，Alice 在查詢時遇到了問題：{str(e)} 🙇‍♀️")

    # ===== 各查詢處理方法 =====

    def _handle_chat(self, user_msg, user_id, reply_token):
        """閒聊對話"""
        memories = self.memory.fetch_relevant_memories(user_msg)
        response = self.llm.generate_chat_response(user_msg, memories)
        self._send(user_id, reply_token, response)

    def _handle_email_query(self, intent_data, user_msg, user_id, reply_token):
        """信件查詢（純查詢）。偵測到擬稿需求時，轉交 Birdie 處理。"""
        from gmail_service import get_recent_emails
        search_keyword = intent_data.get("search_keyword", "")
        emails = get_recent_emails(self.gmail, query=search_keyword)

        if not emails:
            kw_display = f"與「{search_keyword}」相關的" if search_keyword else "符合的相關"
            self._send(user_id, reply_token,
                f"仁哥，信箱中沒有找到{kw_display}信件 📭\n\n"
                "要不要 Alice 幫您換個方向查查看？\n"
                "📚 回覆「查知識庫」→ 搜尋內部專業文件\n"
                "☁️ 回覆「找檔案」→ 搜尋雲端硬碟\n"
                "🌐 回覆「上網查」→ 網際網路搜尋")
            return

        # 偵測擬稿意圖 → 跨角色轉交 Birdie
        draft_keywords = ["回信", "回覆", "擬稿", "草擬", "草稿", "答覆", "寫信"]
        is_drafting = any(kw in user_msg for kw in draft_keywords)

        if is_drafting and self._handoff_fn:
            logger.info("🔄 Alice → Birdie 跨角色轉交：擬稿作業")
            handoff_data = {
                "intent": "Draft_Email",
                "emails": emails,
                "search_keyword": search_keyword,
            }
            self._handoff_fn(handoff_data, user_msg, user_id, reply_token)
            return

        # 純查詢：摘要信件
        memories = self.memory.fetch_relevant_memories(user_msg)
        summary_msg = self.llm.format_email_summary(emails, user_msg, memories, search_keyword)
        self._send(user_id, reply_token, summary_msg)

    def _handle_calendar_query(self, intent_data, user_msg, user_id, reply_token, time_range):
        """行程查詢"""
        from calendar_service import get_events
        tz = pytz.timezone('Asia/Taipei')
        now = datetime.datetime.now(tz)

        start_offset = time_range.get("start_offset", 0)
        end_offset = time_range.get("end_offset", 0)
        label = time_range.get("label", "指定時間")
        search_keyword = intent_data.get("search_keyword", "")

        start_dt = now + datetime.timedelta(days=start_offset)
        end_dt = now + datetime.timedelta(days=end_offset)
        start_str = start_dt.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
        end_str = end_dt.replace(hour=23, minute=59, second=59, microsecond=0).isoformat()
        start_utc = datetime.datetime.fromisoformat(start_str).astimezone(pytz.UTC).isoformat().replace('+00:00', 'Z')
        end_utc = datetime.datetime.fromisoformat(end_str).astimezone(pytz.UTC).isoformat().replace('+00:00', 'Z')

        events = get_events(self.calendar, start_utc, end_utc, query=search_keyword)
        memories = self.memory.fetch_relevant_memories(user_msg)
        final_response = self.llm.format_calendar_response(events, label, user_msg, memories, search_keyword)
        self._send(user_id, reply_token, final_response)

    def _handle_drive_search(self, intent_data, user_msg, user_id, reply_token):
        """雲端檔案搜尋"""
        if not self.drive:
            self._send(user_id, reply_token, "仁哥抱歉，尚未授權 Google Drive 服務 🙇‍♀️")
            return

        search_keyword = intent_data.get("search_keyword", user_msg)
        files = self.drive.search_files_by_keyword(search_keyword)
        if files:
            final_msg = self.llm.format_drive_search_results(files, user_msg)
            self._send(user_id, reply_token, final_msg)
        else:
            self._send(user_id, reply_token,
                f"仁哥，雲端硬碟中沒有找到與「{search_keyword}」相關的檔案 📭\n\n"
                "要不要 Alice 幫您換個方向查查看？\n"
                "📚 回覆「查知識庫」→ 搜尋內部專業文件\n"
                "📧 回覆「查信件」→ 搜尋電子郵件\n"
                "🌐 回覆「上網查」→ 網際網路搜尋")

    def _handle_knowledge_query(self, intent_data, user_msg, user_id, reply_token):
        """知識庫查詢（NotebookLM）"""
        domain = intent_data.get("domain", "it")
        search_keyword = intent_data.get("search_keyword", user_msg)
        domain_names = {"infosec": "資通安全", "it": "資訊科技", "trends": "國際趨勢"}
        domain_name = domain_names.get(domain, "專業領域")

        self._send(user_id, reply_token,
            f"📚 沒問題，Alice 正在查看「{domain_name}」知識庫為您尋找答案，請稍候片刻... ⏳")

        thread = threading.Thread(
            target=self._async_notebooklm_query,
            args=(user_id, search_keyword, domain)
        )
        thread.start()

    def _async_notebooklm_query(self, user_id: str, query: str, domain: str):
        """非同步 NotebookLM 查詢（含降級機制）"""
        try:
            result = self.notebooklm.query_advisor(query, domain)
            raw_answer = result.get("answer", "")
            source_url = result.get("source_url", "")

            if not raw_answer or len(raw_answer) < 20 or "抱歉" in raw_answer[:20]:
                logger.warning(f"⚠️ NotebookLM 回答不足，降級為網路搜尋")
                self._fallback_web_search(user_id, query, "知識庫目前暫時無法提供完整回答")
                return

            formatted_report = self.llm.format_domain_advisor_reply(query, domain, raw_answer, source_url)
            self.line.push_text(formatted_report, to_user_id=user_id)
            logger.info(f"✅ Alice NotebookLM 查詢完成 (用戶: {user_id})")
        except Exception as e:
            logger.error(f"❌ Alice 知識庫查詢失敗: {e}")
            self._fallback_web_search(user_id, query, "知識庫查詢異常")

    def _handle_web_search(self, intent_data, user_msg, user_id, reply_token):
        """網際網路搜尋"""
        search_keyword = intent_data.get("search_keyword", user_msg)
        self._send(user_id, reply_token,
            f"🌐 收到，Alice 正在透過網路搜尋「{search_keyword}」的最新資訊，請稍候... ⏳")

        thread = threading.Thread(
            target=self._async_web_search,
            args=(user_id, search_keyword)
        )
        thread.start()

    def _async_web_search(self, user_id: str, query: str):
        """非同步執行網際網路搜尋"""
        try:
            formatted_report = self.llm.perform_web_search(query)
            self.line.push_text(formatted_report, to_user_id=user_id)
            logger.info(f"✅ Alice 網路搜尋完成 (用戶: {user_id})")
        except Exception as e:
            logger.error(f"❌ Alice 網路搜尋失敗: {e}")
            self.line.push_text(
                f"報告仁哥，剛才在網路搜尋「{query}」時，技術上突然卡住了... 🙇‍♀️",
                to_user_id=user_id)

    def _fallback_web_search(self, user_id: str, query: str, reason: str):
        """知識庫 → 網路搜尋降級"""
        try:
            logger.info(f"🔄 Alice 啟動降級搜尋: {reason}")
            fallback = self.llm.perform_web_search(query)
            self.line.push_text(
                f"{fallback}\n\n"
                f"⚠️ 注意：{reason}，以上為 Alice 從網路搜尋到的資訊。",
                to_user_id=user_id)
        except Exception as fallback_err:
            logger.error(f"❌ Alice 降級搜尋也失敗: {fallback_err}")
            self.line.push_text(
                "仁哥抱歉，知識庫和網路搜尋目前都暫時出了狀況 🙇‍♀️\n"
                "請稍後再試一次。",
                to_user_id=user_id)

    def _handle_tasks_query(self, user_msg, user_id, reply_token):
        """Google Tasks 查詢"""
        if not self.tasks:
            self._send(user_id, reply_token, "仁哥抱歉，尚未授權 Google Tasks 服務 🙇‍♀️")
            return
        from tasks_service import list_tasks
        raw_tasks = list_tasks(self.tasks)
        memories = self.memory.fetch_relevant_memories(user_msg)
        final_msg = self.llm.format_tasks_response(raw_tasks, user_msg, memories)
        self._send(user_id, reply_token, final_msg)

    def _send(self, user_id, reply_token, text):
        """Alice 的統一回覆"""
        send_response(self.line, user_id, reply_token, text)
