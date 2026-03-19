import datetime
import time
import pytz
from calendar_service import get_todays_events, get_events
from gmail_service import get_recent_emails, create_gmail_draft
from tasks_service import create_google_task
from contacts_service import create_contact, ensure_contact_group, add_contact_to_group, CONTACT_GROUPS
from llm_service import LLMService
from config import logger
from line_service import LineService
from memory_service import MemoryService
from pinecone_memory import PineconeMemory
from drive_service import DriveService
from drive_organizer import DriveOrganizer
from notebooklm_service import NotebookLMService
import threading

class ActionDispatcher:
    """處理各類意圖對應的業務邏輯。"""
    
    def __init__(self, line_service: LineService, llm_service: LLMService,
                 gmail, calendar, tasks, sheets, drive=None, people=None):
        self.line = line_service
        self.llm = llm_service
        self.gmail = gmail
        self.calendar = calendar
        self.tasks = tasks
        self.sheets = sheets
        self.people = people
        
        # 初始化 NotebookLM 專家服務
        self.notebooklm = NotebookLMService()

        # 初始化 Pinecone 向量記憶服務
        pinecone_mem = PineconeMemory()
        self.memory = MemoryService(sheets, llm_service, pinecone_mem)

        # 初始化 Drive 整理代理
        if drive:
            drive_svc = DriveService(drive)
            self.drive_organizer = DriveOrganizer(drive_svc, llm_service)
            logger.info("✅ Drive 整理代理就緒")
        else:
            self.drive_organizer = None
            logger.warning("⚠️ Drive 服務未就緒，整理功能停用")

        # 澄清意圖暫存（使用者選擇前保存原始查詢）
        self._pending_clarification = {}
        # 信件查詢上下文暫存（用於草擬回信時缺乏關鍵字時的推斷）
        self._user_email_context = {}

    # 確認/取消動作的關鍵字（規則式判斷，不依賴 LLM）
    CONFIRM_KEYWORDS = {"好", "好的", "可以", "執行", "同意", "沒問題", "ok", "OK", "去做吧", "做吧", "對", "是", "嗯"}
    CANCEL_KEYWORDS = {"不要", "不用", "取消", "算了", "停", "不", "別", "放棄"}

    # 澄清選項對照表
    INTENT_MENU = {
        1: "Query_Project_Advisor",
        2: "Query_Email",
        3: "Search_Drive",
        4: "Search_Web",
    }
    INTENT_LABELS = {
        "Query_Project_Advisor": ("📚", "知識庫（內部專業文件）"),
        "Query_Email":           ("📧", "電子郵件"),
        "Search_Drive":          ("☁️", "雲端硬碟檔案"),
        "Search_Web":            ("🌐", "網際網路即時搜尋"),
    }

    def dispatch(self, intent_data, user_msg: str, user_id: str, reply_token: str = None):
        """根據意圖分流行動"""
        if isinstance(intent_data, str):
            intent = intent_data
            time_range = {"start_offset": 0, "end_offset": 0, "label": "今天"}
        else:
            intent = intent_data.get("intent", "Chat")
            time_range = intent_data.get("time_range", {"start_offset": 0, "end_offset": 0, "label": "今天"})
            
        logger.info(f"分派意圖: {intent} | 時間標籤: {time_range.get('label')}")

        # ⚡ 規則式前置：數字快捷選擇攔截（用於澄清流程回覆）
        if user_msg.strip() in ["1", "2", "3", "4"]:
            choice = int(user_msg.strip())
            if self._handle_clarification_choice(user_id, reply_token, choice):
                return

        # 🔑 規則式前置判斷：有待確認提案時，短回覆直接攔截
        if self.drive_organizer and self.drive_organizer.has_pending_proposal(user_id):
            msg_clean = user_msg.strip()
            if msg_clean in self.CONFIRM_KEYWORDS:
                intent = "Confirm_Action"
                logger.info(f"🔑 規則式攔截 → Confirm_Action (有待確認提案)")
            elif msg_clean in self.CANCEL_KEYWORDS:
                intent = "Cancel_Action"
                logger.info(f"🔑 規則式攔截 → Cancel_Action (有待確認提案)")

        try:
            if intent == "Chat":
                # 智慧檢索相關記憶，進行個人化對話
                memories = self.memory.fetch_relevant_memories(user_msg)
                response = self.llm.generate_chat_response(user_msg, memories)
                self._send_response(user_id, reply_token, response)
                
            elif intent == "Memory_Update":
                # 萃取結構化事實並存入 Google Sheets
                fact_data = self.llm.extract_fact_to_remember(user_msg)
                if fact_data and fact_data.get("fact"):
                    cat_label = fact_data.get('category', '')
                    fact_text = fact_data.get('fact', '')
                    result = self.memory.save_memory(fact_data)
                    
                    if result == "new":
                        self._send_response(user_id, reply_token, f"✅ 收到，Alice 已經幫仁哥記下了：\n📁 分類：{cat_label}\n📝 {fact_text}")
                    elif result == "duplicate":
                        self._send_response(user_id, reply_token, f"仁哥，這個 Alice 已經記過了喔 😊\n📝 {fact_text}")
                    elif result == "updated":
                        self._send_response(user_id, reply_token, f"🔄 收到，Alice 已經幫仁哥更新記憶了：\n📁 分類：{cat_label}\n📝 {fact_text}")
                    else:
                        self._send_response(user_id, reply_token, "仁哥抱歉，Alice 在存入記憶時遇到了問題，請稍後再試一次 🙇‍♀️")
                else:
                    self._send_response(user_id, reply_token, "仁哥，Alice 沒有從訊息中找到需要記住的內容，可以再說一次嗎？😊")

            elif intent == "Organize_Drive":
                # 觸發 Drive 整理掃描與提案
                if not self.drive_organizer:
                    self._send_response(user_id, reply_token, "仁哥抱歉，Drive 服務尚未就緒 🙇‍♀️")
                    return
                self._send_response(user_id, reply_token, "📂 收到！Alice 正在掃描雲端硬碟，請稍候... ⏳")
                result = self.drive_organizer.scan_and_propose(user_id)
                # 提案需透過 push 發送（reply_token 已用完）
                self.line.push_text(result, to_user_id=user_id)

            elif intent == "Confirm_Action":
                # 確認執行待處理的操作
                if self.drive_organizer and self.drive_organizer.has_pending_proposal(user_id):
                    self._send_response(user_id, reply_token, "🚀 收到！Alice 正在執行整理，請稍候... ⏳")
                    result = self.drive_organizer.confirm_and_execute(user_id)
                    self.line.push_text(result, to_user_id=user_id)
                else:
                    # 沒有待確認提案，當作一般對話
                    memories = self.memory.fetch_relevant_memories(user_msg)
                    response = self.llm.generate_chat_response(user_msg, memories)
                    self._send_response(user_id, reply_token, response)

            elif intent == "Cancel_Action":
                # 取消待處理的操作
                if self.drive_organizer and self.drive_organizer.has_pending_proposal(user_id):
                    result = self.drive_organizer.cancel_proposal(user_id)
                    self._send_response(user_id, reply_token, result)
                else:
                    # 沒有待確認提案，當作一般對話
                    memories = self.memory.fetch_relevant_memories(user_msg)
                    response = self.llm.generate_chat_response(user_msg, memories)
                    self._send_response(user_id, reply_token, response)
            
            elif intent == "Proactive_Process":
                # 觸發主動處理流程
                self._send_response(user_id, reply_token, "📊 收到！Alice 正在彙整今日行程與郵件，為仁哥製作簡報中... ⏳")
                result = self.handle_proactive_process()
                self.line.push_text(result, to_user_id=user_id)
                
            elif intent == "Query_Calendar":
                # 加入進度通知
                self._send_response(user_id, reply_token, f"📅 收到！Alice 正在翻閱您的「{time_range.get('label', '行事曆')}」... ⏳")
                reply_token = None # 後續使用 push

                tz = pytz.timezone('Asia/Taipei')
                now = datetime.datetime.now(tz)
                
                # 計算開始與結束時間
                start_offset = time_range.get("start_offset", 0)
                end_offset = time_range.get("end_offset", 0)
                label = time_range.get("label", "指定時間")
                search_keyword = intent_data.get("search_keyword", "")
                
                start_dt = now + datetime.timedelta(days=start_offset)
                end_dt = now + datetime.timedelta(days=end_offset)
                
                # 把開始設為那天的 00:00:00，結束設為那天的 23:59:59 (依台北時區)
                start_str = start_dt.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
                end_str = end_dt.replace(hour=23, minute=59, second=59, microsecond=0).isoformat()
                
                # 將時區轉換為 UTC 以符合 Google Calendar API 需求
                start_utc = datetime.datetime.fromisoformat(start_str).astimezone(pytz.UTC).isoformat().replace('+00:00', 'Z')
                end_utc = datetime.datetime.fromisoformat(end_str).astimezone(pytz.UTC).isoformat().replace('+00:00', 'Z')
                
                events = get_events(self.calendar, start_utc, end_utc, query=search_keyword)
                
                # 從記憶中提取可能相關的資訊，讓秘書分析更貼心
                memories = self.memory.fetch_relevant_memories(user_msg)
                
                # 請 LLM 格式化回覆 (加入秘書視角)
                final_response = self.llm.format_calendar_response(events, label, user_msg, memories, search_keyword)
                self.line.push_text(final_response, to_user_id=user_id)
                
            elif intent == "Query_Tasks":
                # 查詢 Google Tasks
                if self.tasks:
                    self._send_response(user_id, reply_token, "✅ 沒問題，Alice 正在查看您的待辦事項清單... ⏳")
                    reply_token = None

                    from tasks_service import list_tasks
                    raw_tasks = list_tasks(self.tasks)
                    # 結合記憶與人設進行格式化
                    memories = self.memory.fetch_relevant_memories(user_msg)
                    final_msg = self.llm.format_tasks_response(raw_tasks, user_msg, memories)
                    self.line.push_text(final_msg, to_user_id=user_id)
                else:
                    self._send_response(user_id, reply_token, "仁哥抱歉，尚未授權 Google Tasks 服務 🙇‍♀️")

            elif intent == "Search_Drive":
                # 搜尋 Google Drive
                if self.drive_organizer and self.drive_organizer.drive:
                    search_keyword = intent_data.get("search_keyword", user_msg)
                    self._send_response(user_id, reply_token, f"📂 好的！Alice 正在雲端硬碟中搜尋「{search_keyword}」... ⏳")
                    reply_token = None

                    files = self.drive_organizer.drive.search_files_by_keyword(search_keyword)
                    if files:
                        final_msg = self.llm.format_drive_search_results(files, user_msg)
                        self.line.push_text(final_msg, to_user_id=user_id)
                    else:
                        self.line.push_text(
                            f"仁哥，雲端硬碟中沒有找到與「{search_keyword}」相關的檔案 📭\n\n"
                            "要不要 Alice 幫您換個方向查查看？\n"
                            "📚 回覆「查知識庫」→ 搜尋內部專業文件\n"
                            "📧 回覆「查信件」→ 搜尋電子郵件\n"
                            "🌐 回覆「上網查」→ 網際網路搜尋", to_user_id=user_id)
                else:
                    self._send_response(user_id, reply_token, "仁哥抱歉，尚未授權 Google Drive 服務 🙇‍♀️")

            elif intent == "Visual_Assistant":
                # 引導使用者傳送圖片
                msg = "📸 好的，仁哥！\n您可以現在傳送「名片」、「會議筆記」或「活動海報」的照片給我，Alice 會立刻為您分析並自動建立聯絡人或行程叮嚀喔！😊"
                self._send_response(user_id, reply_token, msg)

            elif intent == "Query_Email":
                search_keyword = intent_data.get("search_keyword", "")
                self._send_response(user_id, reply_token, f"📧 收到，Alice 正在您的信箱中檢索「{search_keyword if search_keyword else '最新郵件'}」... ⏳")
                reply_token = None

                # 紀錄上下文，方便後續擬稿時參考
                self._user_email_context[user_id] = search_keyword
                
                emails = get_recent_emails(self.gmail, query=search_keyword)
                
                if emails:
                    memories = self.memory.fetch_relevant_memories(user_msg)
                    # 摘要分析信件
                    summary_msg = self.llm.format_email_summary(emails, user_msg, memories, search_keyword)
                    self.line.push_text(summary_msg, to_user_id=user_id)
                else:
                    kw_display = f"與「{search_keyword}」相關的" if search_keyword else "符合的相關"
                    self.line.push_text(
                        f"仁哥，信箱中沒有找到{kw_display}信件 📭\n\n"
                        "要不要 Alice 幫您換個方向查查看？\n"
                        "📚 回覆「查知識庫」→ 搜尋內部專業文件\n"
                        "☁️ 回覆「找檔案」→ 搜尋雲端硬碟\n"
                        "🌐 回覆「上網查」→ 網際網路搜尋", to_user_id=user_id)
            
            elif intent == "Draft_Email":
                # 若無搜尋關鍵字，嘗試擷取上一次 Query_Email 的上下文
                search_keyword = intent_data.get("search_keyword", "")
                if not search_keyword and user_id in self._user_email_context:
                    search_keyword = self._user_email_context[user_id]

                self._send_response(user_id, reply_token, f"✍️ 好的，Alice 正在讀取信件並為您草擬回覆... ⏳")
                reply_token = None

                draft_instruction = intent_data.get("draft_instruction", user_msg)
                emails = get_recent_emails(self.gmail, query=search_keyword)
                
                if emails:
                    memories = self.memory.fetch_relevant_memories(user_msg)
                    # 挑選第一封信（假設為最相關）進行草稿生成
                    target_email = emails[0]
                    draft_body = self.llm.generate_email_draft_reply(target_email, draft_instruction, memories)
                    
                    # 呼叫 Gmail API 建立草稿
                    create_gmail_draft(
                        self.gmail,
                        to_email=target_email['sender'],
                        subject=f"Re: {target_email['subject']}",
                        body_text=draft_body,
                        thread_id=target_email.get('threadId')
                    )
                    
                    self.line.push_text(f"✅ 仁哥，已經幫您在 Gmail 草擬好回信給「{target_email['sender']}」了！\n\n草稿內容如下：\n{draft_body}", to_user_id=user_id)
                else:
                    self.line.push_text(f"仁哥，我找不到相關的信件來回覆 📭，請告訴我要回信給誰或主旨是什麼。", to_user_id=user_id)
            
            elif intent == "Query_Project_Advisor":
                domain = intent_data.get("domain", "it")
                search_keyword = intent_data.get("search_keyword", user_msg)
                
                # 立即回覆告知正在查詢中
                domain_names = {"infosec": "資通安全", "it": "資訊科技", "trends": "國際趨勢"}
                domain_name = domain_names.get(domain, "專業領域")
                self._send_response(user_id, reply_token, f"📚 沒問題，Alice 正在查看「{domain_name}」知識庫為您尋找答案，請稍候片刻... ⏳")
                
                # 開啟執行緒進行非同步查詢與回傳
                thread = threading.Thread(
                    target=self._async_notebooklm_query,
                    args=(user_id, search_keyword, domain)
                )
                thread.start()

            elif intent == "Search_Web":
                search_keyword = intent_data.get("search_keyword", user_msg)
                
                # 立即回覆告知正在搜尋中
                self._send_response(user_id, reply_token, f"🌐 收到，Alice 正在透過網路搜尋「{search_keyword}」的最新資訊，請稍候... ⏳")
                
                # 開啟執行緒進行非同步搜尋
                thread = threading.Thread(
                    target=self._async_web_search,
                    args=(user_id, search_keyword)
                )
                thread.start()

            elif intent == "Clarify_Intent":
                self._handle_clarify(intent_data, user_msg, user_id, reply_token)

        except Exception as e:
            logger.error(f"處理分派時異常: {e}")
            self._send_response(user_id, reply_token, f"仁哥抱歉，Alice 處理時遇到了問題：{str(e)} 🙇‍♀️")

    def _async_web_search(self, user_id: str, query: str):
        """非同步執行網際網路搜尋並推送結果"""
        try:
            # 1. 執行搜尋並格式化回覆 (利用 Gemini 2.0 內建搜尋能力)
            formatted_report = self.llm.perform_web_search(query)
            
            # 2. 透過 LINE Push 推送結果
            self.line.push_text(formatted_report, to_user_id=user_id)
            
            logger.info(f"✅ 網際網路搜尋任務完成 (用戶: {user_id})")
        except Exception as e:
            logger.error(f"❌ _async_web_search 執行失敗: {e}")
            self.line.push_text(f"報告仁哥，剛才在網路搜尋「{query}」時，技術上突然卡住了... 🙇‍♀️", to_user_id=user_id)

    def _async_notebooklm_query(self, user_id: str, query: str, domain: str):
        """非同步執行 NotebookLM 查詢並推送結果（含降級機制）"""
        try:
            # 1. 向 NotebookLM 專家查詢
            result = self.notebooklm.query_advisor(query, domain)
            raw_answer = result.get("answer", "")
            source_url = result.get("source_url", "")
            
            # 2. 降級判斷：知識庫回答不足
            if not raw_answer or len(raw_answer) < 20 or "抱歉" in raw_answer[:20]:
                logger.warning(f"⚠️ NotebookLM 回答不足 (長度:{len(raw_answer)})，降級為網路搜尋")
                self._fallback_web_search(user_id, query, "知識庫目前暫時無法提供完整回答")
                return
            
            # 3. 透過 LLM 轉化為 Alice 的口吻報告
            formatted_report = self.llm.format_domain_advisor_reply(query, domain, raw_answer, source_url)
            
            # 4. 透過 LINE Push 推送結果
            self.line.push_text(formatted_report, to_user_id=user_id)
            
            logger.info(f"✅ NotebookLM 查詢任務完成 (用戶: {user_id})")
        except Exception as e:
            logger.error(f"❌ _async_notebooklm_query 執行失敗: {e}")
            # 降級為網路搜尋
            self._fallback_web_search(user_id, query, f"知識庫查詢異常")

    def _fallback_web_search(self, user_id: str, query: str, reason: str):
        """當知識庫失敗時，降級為網路搜尋"""
        try:
            logger.info(f"🔄 啟動降級搜尋: {reason}")
            fallback = self.llm.perform_web_search(query)
            self.line.push_text(
                f"{fallback}\n\n"
                f"⚠️ 注意：{reason}，以上為 Alice 從網路搜尋到的資訊。",
                to_user_id=user_id)
        except Exception as fallback_err:
            logger.error(f"❌ 降級搜尋也失敗: {fallback_err}")
            self.line.push_text(
                f"仁哥抱歉，知識庫和網路搜尋目前都暫時出了狀況 🙇‍♀️\n"
                f"請稍後再試一次。",
                to_user_id=user_id)

    def _handle_clarify(self, intent_data, user_msg, user_id, reply_token):
        """處理 Clarify_Intent：暫存原始查詢並傳送選項給使用者"""
        candidates = intent_data.get("candidates", [])
        
        # 暫存原始查詢
        self._pending_clarification[user_id] = {
            "original_query": user_msg,
            "original_intent_data": intent_data,
            "candidates": candidates,
            "timestamp": time.time()
        }
        
        # 組合選項訊息
        options = []
        for num, intent_key in self.INTENT_MENU.items():
            emoji, label = self.INTENT_LABELS.get(intent_key, ("❓", "其他"))
            options.append(f"{num}️⃣ {emoji} {label}")
        
        ambiguity = intent_data.get("ambiguity_reason", "")
        reason_text = f"\n（{ambiguity}）" if ambiguity else ""
        
        msg = (
            f"仁哥，關於「{user_msg}」，{reason_text}\n"
            f"請問您想從哪裡查詢呢？😊\n\n"
            + "\n".join(options) +
            "\n\n直接回覆數字就好 ✨"
        )
        self._send_response(user_id, reply_token, msg)

    def _handle_clarification_choice(self, user_id, reply_token, choice):
        """處理使用者的數字選擇。返回 True 表示已處理，False 表示非澄清流程。"""
        pending = self._pending_clarification.get(user_id)
        
        # 找不到暫存 → 不攔截，讓正常流程處理
        if not pending:
            return False
        
        # 過期檢查（5 分鐘）
        if time.time() - pending["timestamp"] > 300:
            del self._pending_clarification[user_id]
            self._send_response(user_id, reply_token,
                "仁哥，這個查詢已經超過 5 分鐘了 ⏰\n"
                "麻煩您重新提問一次好嗎？")
            return True
        
        target_intent = self.INTENT_MENU.get(choice)
        if not target_intent:
            return False
        
        original_query = pending["original_query"]
        original_data = pending.get("original_intent_data", {})
        del self._pending_clarification[user_id]  # 清除暫存
        
        # 統一雙訊息模式：reply 確認 → push 結果
        emoji, label = self.INTENT_LABELS.get(target_intent, ("", ""))
        self._send_response(user_id, reply_token,
            f"✅ 收到！Alice 正在從「{label}」查詢「{original_query}」... ⏳")
        
        # 重組 intent_data 並轉發（reply_token 設為 None，後續結果走 push）
        original_data["intent"] = target_intent
        original_data["search_keyword"] = original_data.get("search_keyword", original_query)
        # 如果選的是知識庫，需要 domain
        if target_intent == "Query_Project_Advisor" and not original_data.get("domain"):
            original_data["domain"] = "it"  # 預設 IT
        
        logger.info(f"🔄 澄清轉發: {target_intent} | 查詢: {original_query}")
        self.dispatch(original_data, original_query, user_id, reply_token=None)
        return True

    def _send_response(self, user_id, reply_token, text):
        """核心回覆邏輯：優先使用 reply_token，失敗則使用 push_text"""
        if reply_token:
            success = self.line.reply_text(reply_token, text)
            if success: return
        
        self.line.push_text(text, to_user_id=user_id)

    def handle_proactive_process(self):
        """執行主動處理邏輯並回傳報告字串"""
        if not all([self.gmail, self.calendar, self.tasks]):
            return "仁哥抱歉，Google 服務授權不完整，Alice 暫時無法處理主動任務 🙇‍♀️"
        
        try:
            # 檢查未來 2 天 (今天 + 明天) 的行程
            from calendar_service import get_events
            tz = pytz.timezone('Asia/Taipei')
            now = datetime.datetime.now(tz)
            start_utc = now.replace(hour=0, minute=0, second=0).astimezone(pytz.UTC).isoformat().replace('+00:00', 'Z')
            end_utc = (now + datetime.timedelta(days=1)).replace(hour=23, minute=59, second=59).astimezone(pytz.UTC).isoformat().replace('+00:00', 'Z')
            
            events = get_events(self.calendar, start_utc, end_utc)
            emails = get_recent_emails(self.gmail)
            
            # 使用 LLM 分析
            action_data = self.llm.analyze_for_actions(events, emails)
            
            # 執行 Tasks
            tasks_created = 0
            for t in action_data.get('tasks', []):
                create_google_task(self.tasks, t.get('title'), t.get('notes'), t.get('due'))
                tasks_created += 1
            
            # 執行 Drafts
            drafts_created = 0
            for d in action_data.get('drafts', []):
                create_gmail_draft(self.gmail, d.get('to'), d.get('subject'), d.get('body'), d.get('threadId'))
                drafts_created += 1
                
            briefing = action_data.get('briefing', '已為您處理完畢。')
            return f"📋 Alice 處理報告\n{briefing}\n\n已幫仁哥建立 {tasks_created} 項待辦任務、{drafts_created} 封回覆草稿 ✅"
            
        except Exception as e:
            logger.error(f"主動處理失敗: {e}")
            return f"仁哥抱歉，Alice 在處理時遇到了問題：{str(e)} 🙇‍♀️"

    def dispatch_image(self, image_bytes: bytes, user_id: str, reply_token: str):
        """處理收到的圖片訊息"""
        logger.info("分派圖片處理")
        self._send_response(user_id, reply_token, "📸 收到圖片！Alice 正在幫您分析並處理成結構化資料中，請稍候... ⏳")
        try:
            analysis_data = self.llm.analyze_image_for_actions(image_bytes)
            
            # 如果回傳的是純文字錯誤訊息，直接推送
            if isinstance(analysis_data, str):
                self.line.push_text(analysis_data, to_user_id=user_id)
                return

            tasks_created = 0
            contacts_created = 0
            
            # 建立任務
            for t in analysis_data.get('tasks', []):
                if self.tasks:
                    create_google_task(self.tasks, t.get('title'), t.get('notes'), t.get('due'))
                    tasks_created += 1
            
            # 建立聯絡人（附帶名片影像）並加入群組
            contacts_group_info = []  # 用於回報訊息
            for c in analysis_data.get('contacts', []):
                if self.people:
                    created = create_contact(
                        self.people, 
                        name=c.get('name', ''), 
                        company=c.get('company', ''), 
                        job_title=c.get('job_title', ''), 
                        email=c.get('email', ''), 
                        phone=c.get('phone', ''),
                        photo_bytes=image_bytes
                    )
                    contacts_created += 1

                    # 取得 LLM 判斷的群組分類（若不在清單內則 fallback 為「其他」）
                    raw_group = c.get('contact_group', '其他').strip()
                    group_name = raw_group if raw_group in CONTACT_GROUPS else '其他'

                    # 確保群組存在並加入聯絡人
                    if created:
                        contact_resource = created.get('resourceName')
                        group_resource = ensure_contact_group(self.people, group_name)
                        if contact_resource and group_resource:
                            add_contact_to_group(self.people, contact_resource, group_resource)
                            contacts_group_info.append(f"{c.get('name', '未知')} → 🏷️ {group_name}")
                        else:
                            contacts_group_info.append(f"{c.get('name', '未知')} → ⚠️ 群組分類失敗")

            briefing = analysis_data.get('briefing', '已為您處理圖片完畢。')
            
            # 組合成果
            summary_parts = []
            if tasks_created > 0:
                summary_parts.append(f"✅ 自動建立了 {tasks_created} 項 Google 待辦任務")
            if contacts_created > 0:
                group_detail = "\n  ".join(contacts_group_info) if contacts_group_info else ""
                summary_parts.append(
                    f"📇 自動建立了 {contacts_created} 筆 Google 聯絡人\n  {group_detail}"
                )
            
            if summary_parts:
                briefing += "\n\n" + "\n".join(summary_parts)

            self.line.push_text(briefing, to_user_id=user_id)
        except Exception as e:
            logger.error(f"圖片分析分派失敗: {e}", exc_info=True)
            self.line.push_text("仁哥抱歉，Alice在處理這張圖片時遇到了問題 🙇‍♀️", to_user_id=user_id)

