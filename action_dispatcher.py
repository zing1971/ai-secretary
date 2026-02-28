from calendar_service import get_todays_events
from gmail_service import get_recent_emails, create_gmail_draft
from tasks_service import create_google_task
from llm_service import LLMService
from config import logger
from line_service import LineService
from memory_service import MemoryService

class ActionDispatcher:
    """處理各類意圖對應的業務邏輯。"""
    
    def __init__(self, line_service: LineService, llm_service: LLMService, gmail, calendar, tasks, sheets):
        self.line = line_service
        self.llm = llm_service
        self.gmail = gmail
        self.calendar = calendar
        self.tasks = tasks
        self.sheets = sheets
        self.memory = MemoryService(sheets)

    def dispatch(self, intent: str, user_msg: str, user_id: str, reply_token: str = None):
        """根據意圖分流行動"""
        logger.info(f"分派意圖: {intent}")
        
        try:
            if intent == "Chat":
                # 獲取長期記憶並進行個人化對話
                memories = self.memory.fetch_all_memories()
                response = self.llm.generate_chat_response(user_msg, memories)
                self._send_response(user_id, reply_token, response)
                
            elif intent == "Memory_Update":
                # 萃取事實並存入 Google Sheets
                fact = self.llm.extract_fact_to_remember(user_msg)
                if fact:
                    if self.memory.save_memory(fact):
                        self._send_response(user_id, reply_token, f"✅ 已為您記住：{fact}")
                    else:
                        self._send_response(user_id, reply_token, "❌ 抱歉老闆，存入記憶時發生錯誤，請稍後再試。")
                else:
                    self._send_response(user_id, reply_token, "抱歉，我無法從您的訊息中萃取出要記住的事實。")
            
            elif intent == "Proactive_Process":
                # 觸發主動處理流程
                result = self.handle_proactive_process()
                self._send_response(user_id, reply_token, result)
                
            elif intent == "Query_Calendar":
                events = get_todays_events(self.calendar)
                msg = "\n".join(events) if events else "今天沒有排定行程。"
                self._send_response(user_id, reply_token, f"【今日行程】\n{msg}")
                
            elif intent == "Query_Email":
                emails = get_recent_emails(self.gmail)
                if emails:
                    summaries = [e['summary_text'] for e in emails[:5]]
                    msg = "\n".join(summaries)
                    self._send_response(user_id, reply_token, f"【最新信件】\n{msg}")
                else:
                    self._send_response(user_id, reply_token, "沒有偵測到未讀信件。")
        except Exception as e:
            logger.error(f"處理分派時異常: {e}")
            self._send_response(user_id, reply_token, f"系統處理發生異常: {str(e)}")

    def _send_response(self, user_id, reply_token, text):
        """核心回覆邏輯：優先使用 reply_token，失敗則使用 push_text"""
        if reply_token:
            success = self.line.reply_text(reply_token, text)
            if success: return
        
        self.line.push_text(text, to_user_id=user_id)

    def handle_proactive_process(self):
        """執行主動處理邏輯並回傳報告字串"""
        if not all([self.gmail, self.calendar, self.tasks]):
            return "抱歉老闆，Google 服務授權不全，無法處理主動任務。"
        
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
            return f"【秘書處理報告】\n{briefing}\n\n已成功建立 {tasks_created} 項任務與 {drafts_created} 封草稿。"
            
        except Exception as e:
            logger.error(f"主動處理失敗: {e}")
            return f"主動處理時發生錯誤：{str(e)}"
