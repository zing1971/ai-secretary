import datetime
import pytz
from calendar_service import get_todays_events, get_events
from gmail_service import get_recent_emails, create_gmail_draft
from tasks_service import create_google_task
from contacts_service import create_contact
from llm_service import LLMService
from config import logger
from line_service import LineService
from memory_service import MemoryService
from pinecone_memory import PineconeMemory
from drive_service import DriveService
from drive_organizer import DriveOrganizer

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

    # 確認/取消動作的關鍵字（規則式判斷，不依賴 LLM）
    CONFIRM_KEYWORDS = {"好", "好的", "可以", "執行", "同意", "沒問題", "ok", "OK", "去做吧", "做吧", "對", "是", "嗯"}
    CANCEL_KEYWORDS = {"不要", "不用", "取消", "算了", "停", "不", "別", "放棄"}

    def dispatch(self, intent_data, user_msg: str, user_id: str, reply_token: str = None):
        """根據意圖分流行動"""
        if isinstance(intent_data, str):
            intent = intent_data
            time_range = {"start_offset": 0, "end_offset": 0, "label": "今天"}
        else:
            intent = intent_data.get("intent", "Chat")
            time_range = intent_data.get("time_range", {"start_offset": 0, "end_offset": 0, "label": "今天"})
            
        logger.info(f"分派意圖: {intent} | 時間標籤: {time_range.get('label')}")

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
                result = self.handle_proactive_process()
                self._send_response(user_id, reply_token, result)
                
            elif intent == "Query_Calendar":
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
                self._send_response(user_id, reply_token, final_response)
                
            elif intent == "Query_Tasks":
                # 查詢 Google Tasks
                if self.tasks:
                    from tasks_service import list_tasks
                    raw_tasks = list_tasks(self.tasks)
                    # 結合記憶與人設進行格式化
                    memories = self.memory.fetch_relevant_memories(user_msg)
                    final_msg = self.llm.format_tasks_response(raw_tasks, user_msg, memories)
                    self._send_response(user_id, reply_token, final_msg)
                else:
                    self._send_response(user_id, reply_token, "仁哥抱歉，尚未授權 Google Tasks 服務 🙇‍♀️")

            elif intent == "Visual_Assistant":
                # 引導使用者傳送圖片
                msg = "📸 好的，仁哥！\n您可以現在傳送「名片」、「會議筆記」或「活動海報」的照片給我，Alice 會立刻為您分析並自動建立聯絡人或行程叮嚀喔！😊"
                self._send_response(user_id, reply_token, msg)

            elif intent == "Query_Email":
                search_keyword = intent_data.get("search_keyword", "")
                emails = get_recent_emails(self.gmail, query=search_keyword)
                
                if emails:
                    # 簡單判別是否為擬稿指令
                    draft_keywords = ["回信", "回覆", "擬稿", "草擬", "草稿", "答覆", "寫信"]
                    is_drafting = any(kw in user_msg for kw in draft_keywords)
                    memories = self.memory.fetch_relevant_memories(user_msg)
                    
                    if is_drafting:
                        # 挑選第一封信（假設為最相關）進行草稿生成
                        target_email = emails[0]
                        draft_body = self.llm.generate_email_draft_reply(target_email, user_msg, memories)
                        
                        # 呼叫 Gmail API 建立草稿
                        create_gmail_draft(
                            self.gmail,
                            to=target_email['sender'],
                            subject=f"Re: {target_email['subject']}",
                            body=draft_body,
                            thread_id=target_email.get('threadId')
                        )
                        
                        self._send_response(user_id, reply_token, f"✅ 仁哥，已經幫您在 Gmail 草擬好回信給「{target_email['sender']}」了！\n\n草稿內容如下：\n{draft_body}")
                    else:
                        # 摘要分析信件
                        summary_msg = self.llm.format_email_summary(emails, user_msg, memories, search_keyword)
                        self._send_response(user_id, reply_token, summary_msg)
                else:
                    self._send_response(user_id, reply_token, "仁哥，為您搜尋後目前沒有符合的相關信件。")
        except Exception as e:
            logger.error(f"處理分派時異常: {e}")
            self._send_response(user_id, reply_token, f"仁哥抱歉，Alice 處理時遇到了問題：{str(e)} 🙇‍♀️")

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
            events = get_todays_events(self.calendar)
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
            
            # 建立聯絡人（附帶名片影像）
            for c in analysis_data.get('contacts', []):
                if self.people:
                    create_contact(
                        self.people, 
                        name=c.get('name', ''), 
                        company=c.get('company', ''), 
                        job_title=c.get('job_title', ''), 
                        email=c.get('email', ''), 
                        phone=c.get('phone', ''),
                        photo_bytes=image_bytes
                    )
                    contacts_created += 1

            briefing = analysis_data.get('briefing', '已為您處理圖片完畢。')
            
            # 組合成果
            summary_parts = []
            if tasks_created > 0:
                summary_parts.append(f"✅ 自動建立了 {tasks_created} 項 Google 待辦任務")
            if contacts_created > 0:
                summary_parts.append(f"📇 自動建立了 {contacts_created} 筆 Google 聯絡人")
            
            if summary_parts:
                briefing += "\n\n" + "\n".join(summary_parts)

            self.line.push_text(briefing, to_user_id=user_id)
        except Exception as e:
            logger.error(f"圖片分析分派失敗: {e}", exc_info=True)
            self.line.push_text("仁哥抱歉，Alice在處理這張圖片時遇到了問題 🙇‍♀️", to_user_id=user_id)

