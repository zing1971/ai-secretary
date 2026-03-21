"""
Birdie — ⚙️ 執行管家 動作處理器

負責所有「有副作用」的工作執行動作：
- Organize_Drive: 整理雲端硬碟
- Confirm_Action / Cancel_Action: 確認或取消待處理操作
- Proactive_Process: 每日簡報（建立待辦、擬寫草稿）
- Memory_Update: 記憶管理
- 圖片處理: 分析圖片並建立聯絡人/任務
"""
import datetime
import pytz
import logging
import threading
from collections import defaultdict


from shared.line_responder import send_response
from shared.clarify_handler import CONFIRM_KEYWORDS, CANCEL_KEYWORDS
from contacts_service import (CONTACT_LABELS, get_unlabeled_contacts,
                               build_label_cache, batch_assign_label)

logger = logging.getLogger(__name__)


class BirdieActionHandler:
    """Birdie 的執行分派核心：所有執行類意圖在此處理"""

    # Birdie 負責的意圖清單
    HANDLED_INTENTS = {
        "Organize_Drive", "Organize_Contacts",
        "Confirm_Action", "Cancel_Action",
        "Proactive_Process", "Memory_Update", "Draft_Email",
    }

    def __init__(self, messaging_service, llm_service, gmail, calendar, tasks, sheets,
                 memory_service, drive_organizer=None, people=None):
        self.line = messaging_service
        self.llm = llm_service
        self.gmail = gmail
        self.calendar = calendar
        self.tasks = tasks
        self.sheets = sheets
        self.memory = memory_service
        self.drive_organizer = drive_organizer
        self.people = people

    def can_handle(self, intent: str) -> bool:
        return intent in self.HANDLED_INTENTS

    def has_pending_confirmation(self, user_id: str) -> bool:
        """檢查 Birdie 是否有待確認提案"""
        return self.drive_organizer and self.drive_organizer.has_pending_proposal(user_id)

    def try_intercept_confirm_cancel(self, user_msg, user_id, reply_token):
        """
        規則式攔截：有待確認提案時，短回覆直接判定確認/取消。
        返回攔截後的意圖字串或 None。
        """
        if not self.has_pending_confirmation(user_id):
            return None
        msg_clean = user_msg.strip()
        if msg_clean in CONFIRM_KEYWORDS:
            logger.info("🔑 Birdie 攔截 → Confirm_Action (有待確認提案)")
            return "Confirm_Action"
        elif msg_clean in CANCEL_KEYWORDS:
            logger.info("🔑 Birdie 攔截 → Cancel_Action (有待確認提案)")
            return "Cancel_Action"
        return None

    def dispatch(self, intent_data, user_msg: str, user_id: str, reply_token: str = None):
        """根據意圖分派執行動作"""
        if isinstance(intent_data, str):
            intent = intent_data
        else:
            intent = intent_data.get("intent", "")

        logger.info(f"⚙️ Birdie 處理執行: {intent}")

        try:
            if intent == "Memory_Update":
                self._handle_memory_update(user_msg, user_id, reply_token)

            elif intent == "Organize_Drive":
                self._handle_organize_drive(user_id, reply_token)

            elif intent == "Organize_Contacts":
                self._handle_organize_contacts(user_id, reply_token)

            elif intent == "Confirm_Action":
                self._handle_confirm(user_msg, user_id, reply_token)

            elif intent == "Cancel_Action":
                self._handle_cancel(user_msg, user_id, reply_token)

            elif intent == "Proactive_Process":
                result = self.handle_proactive_process()
                self._send(user_id, reply_token, result)

            elif intent == "Draft_Email":
                self._handle_draft_email(intent_data, user_msg, user_id, reply_token)

        except Exception as e:
            logger.error(f"❌ Birdie 處理執行異常: {e}")
            self._send(user_id, reply_token,
                f"仁哥抱歉，Birdie 在執行時遇到了問題：{str(e)} 🙇‍♀️")

    # ===== 各執行處理方法 =====

    def _handle_memory_update(self, user_msg, user_id, reply_token):
        """記憶更新"""
        fact_data = self.llm.extract_fact_to_remember(user_msg)
        if fact_data and fact_data.get("fact"):
            cat_label = fact_data.get('category', '')
            fact_text = fact_data.get('fact', '')
            result = self.memory.save_memory(fact_data)

            if result == "new":
                self._send(user_id, reply_token,
                    f"✅ 收到，Birdie 已經幫仁哥記下了：\n📁 分類：{cat_label}\n📝 {fact_text}")
            elif result == "duplicate":
                self._send(user_id, reply_token,
                    f"仁哥，這個已經記過了喔 😊\n📝 {fact_text}")
            elif result == "updated":
                self._send(user_id, reply_token,
                    f"🔄 收到，Birdie 已經幫仁哥更新記憶了：\n📁 分類：{cat_label}\n📝 {fact_text}")
            else:
                self._send(user_id, reply_token,
                    "仁哥抱歉，Birdie 在存入記憶時遇到了問題，請稍後再試一次 🙇‍♀️")
        else:
            self._send(user_id, reply_token,
                "仁哥，Birdie 沒有從訊息中找到需要記住的內容，可以再說一次嗎？😊")

    def _handle_organize_drive(self, user_id, reply_token):
        """整理雲端硬碟"""
        if not self.drive_organizer:
            self._send(user_id, reply_token, "仁哥抱歉，Drive 服務尚未就緒 🙇‍♀️")
            return
        self._send(user_id, reply_token, "📂 收到！Birdie 正在掃描雲端硬碟，請稍候... ⏳")
        result = self.drive_organizer.scan_and_propose(user_id)
        self.line.push_text(result, to_user_id=user_id)

    def _handle_organize_contacts(self, user_id, reply_token):
        """整理聯絡人：掃描並批次貼標籤"""
        if not self.people:
            self._send(user_id, reply_token, "仁哥抱歉，聯絡人服務尚未就緒 🙇‍♀️")
            return
        self._send(user_id, reply_token, "📇 收到！Birdie 正在掃描聯絡人清單，請稍候... ⏳")
        threading.Thread(
            target=self._organize_contacts_worker,
            args=(user_id,),
            daemon=True
        ).start()

    def _organize_contacts_worker(self, user_id: str):
        """背景執行：掃描未分類聯絡人並批次貼標籤。
        優化：
          1. 一次性標籤快取 — 避免 N 次 contactGroups().list()
          2. 循序 LLM 分類 — 避免 ThreadPoolExecutor timeout 累積問題
          3. 定時 thread 每 5 分鐘推播進度 — 不依賴筆數，給予穩定反饋
          4. 同標籤滿 10 筆即寫入 — 分類與寫入交錯進行
        """
        try:
            contacts = get_unlabeled_contacts(self.people)
            total = len(contacts)

            if total == 0:
                self.line.push_text("✅ 仁哥，所有聯絡人都已有分類標籤，無需整理！", to_user_id=user_id)
                return

            self.line.push_text(
                f"📋 共找到 {total} 筆未分類聯絡人，Birdie 開始分類中 🏷️",
                to_user_id=user_id
            )

            label_cache = build_label_cache(self.people)
            pending = defaultdict(list)
            summary_count = defaultdict(int)
            success = 0
            failed = 0
            completed = [0]       # mutable，供 timer thread 讀取
            stop_event = threading.Event()

            def timer_reporter():
                while not stop_event.wait(300):   # 每 5 分鐘
                    self.line.push_text(
                        f"⏱️ 分類進行中 {completed[0]}/{total}，請稍候...",
                        to_user_id=user_id
                    )

            timer_thread = threading.Thread(target=timer_reporter, daemon=True)
            timer_thread.start()

            try:
                for i, c in enumerate(contacts):
                    try:
                        label = self.llm.classify_contact_label(
                            name=c['name'],
                            company=c['company'],
                            job_title=c['job_title'],
                            email=c.get('email', ''),
                        )
                    except Exception as e:
                        logger.warning(f"分類失敗 ({c['name']}): {e}")
                        label = '其他'

                    pending[label].append(c['resourceName'])

                    # 同標籤滿 10 筆立即批次寫入
                    if len(pending[label]) >= 10:
                        batch = pending[label][:10]
                        pending[label] = pending[label][10:]
                        ok = batch_assign_label(self.people, batch, label, label_cache)
                        if ok:
                            success += len(batch)
                            summary_count[label] += len(batch)
                        else:
                            failed += len(batch)

                    completed[0] = i + 1
            finally:
                stop_event.set()
                timer_thread.join(timeout=1)

            # 寫入各標籤剩餘尾數
            for label, resource_names in pending.items():
                if resource_names:
                    ok = batch_assign_label(self.people, resource_names, label, label_cache)
                    if ok:
                        success += len(resource_names)
                        summary_count[label] += len(resource_names)
                    else:
                        failed += len(resource_names)

            # 最終摘要
            summary_lines = [
                f"🎉 聯絡人整理完成！共處理 {total} 筆，成功 {success} 筆，失敗 {failed} 筆。",
                "",
                "📊 分類結果："
            ]
            for label in CONTACT_LABELS:
                count = summary_count.get(label, 0)
                if count:
                    summary_lines.append(f"  🏷️ {label}：{count} 人")

            self.line.push_text("\n".join(summary_lines), to_user_id=user_id)

        except Exception as e:
            logger.error(f"整理聯絡人失敗: {e}", exc_info=True)
            self.line.push_text(f"仁哥抱歉，整理聯絡人時發生錯誤：{e} 🙇‍♀️", to_user_id=user_id)

    def _handle_confirm(self, user_msg, user_id, reply_token):
        """確認執行"""
        if self.drive_organizer and self.drive_organizer.has_pending_proposal(user_id):
            self._send(user_id, reply_token, "🚀 收到！Birdie 正在執行整理，請稍候... ⏳")
            result = self.drive_organizer.confirm_and_execute(user_id)
            self.line.push_text(result, to_user_id=user_id)
        else:
            # 沒有待確認提案 → 當作閒聊
            memories = self.memory.fetch_relevant_memories(user_msg)
            response = self.llm.generate_chat_response(user_msg, memories)
            self._send(user_id, reply_token, response)

    def _handle_cancel(self, user_msg, user_id, reply_token):
        """取消操作"""
        if self.drive_organizer and self.drive_organizer.has_pending_proposal(user_id):
            result = self.drive_organizer.cancel_proposal(user_id)
            self._send(user_id, reply_token, result)
        else:
            memories = self.memory.fetch_relevant_memories(user_msg)
            response = self.llm.generate_chat_response(user_msg, memories)
            self._send(user_id, reply_token, response)

    def _handle_draft_email(self, intent_data, user_msg, user_id, reply_token):
        """擬稿回信（由 Alice 跨角色轉交，或直接由 IntentRouter 路由）"""
        from gmail_service import get_recent_emails, create_gmail_draft

        emails = intent_data.get("emails", [])

        # 若無預載信件（直接從 IntentRouter 進來），自行抓取
        if not emails:
            search_keyword = intent_data.get("search_keyword", "")
            emails = get_recent_emails(self.gmail, query=search_keyword) if self.gmail else []

        if not emails:
            self._send(user_id, reply_token,
                "仁哥，Birdie 沒有找到需要回覆的信件 📭\n"
                "可以請您指定寄件人或主旨嗎？例如：「回覆 OOO 的信」")
            return

        target_email = emails[0]
        memories = self.memory.fetch_relevant_memories(user_msg)

        self._send(user_id, reply_token,
            f"✍️ 收到！Birdie 正在為仁哥擬寫回信給「{target_email.get('sender', '對方')}」... ⏳")

        try:
            draft_body = self.llm.generate_email_draft_reply(target_email, user_msg, memories)
            create_gmail_draft(
                self.gmail,
                to_email=target_email['sender'],
                subject=f"Re: {target_email['subject']}",
                body_text=draft_body,
                thread_id=target_email.get('threadId')
            )
            self.line.push_text(
                f"✅ 仁哥，Birdie 已經幫您在 Gmail 草擬好回信了！\n\n"
                f"📧 收件人：{target_email['sender']}\n"
                f"📌 主旨：Re: {target_email['subject']}\n\n"
                f"草稿內容如下：\n{draft_body}\n\n"
                "══════════════\n"
                "— ⚙️ Birdie / 郵件擬稿",
                to_user_id=user_id)
            logger.info(f"✅ Birdie 擬稿完成 (用戶: {user_id})")
        except Exception as e:
            logger.error(f"❌ Birdie 擬稿失敗: {e}")
            self.line.push_text(
                f"仁哥抱歉，Birdie 在擬寫回信時遇到問題：{str(e)} 🙇‍♀️",
                to_user_id=user_id)

    def handle_proactive_process(self) -> str:
        """執行主動處理邏輯並回傳報告字串"""
        if not all([self.gmail, self.calendar, self.tasks]):
            return "仁哥抱歉，Google 服務授權不完整，Birdie 暫時無法處理主動任務 🙇‍♀️"

        try:
            from calendar_service import get_events
            from gmail_service import get_recent_emails, create_gmail_draft
            from tasks_service import create_google_task

            tz = pytz.timezone('Asia/Taipei')
            now = datetime.datetime.now(tz)
            start_utc = now.replace(hour=0, minute=0, second=0).astimezone(pytz.UTC).isoformat().replace('+00:00', 'Z')
            end_utc = (now + datetime.timedelta(days=1)).replace(hour=23, minute=59, second=59).astimezone(pytz.UTC).isoformat().replace('+00:00', 'Z')

            events = get_events(self.calendar, start_utc, end_utc)
            emails = get_recent_emails(self.gmail)

            action_data = self.llm.analyze_for_actions(events, emails)

            tasks_created = 0
            for t in action_data.get('tasks', []):
                create_google_task(self.tasks, t.get('title'), t.get('notes'), t.get('due'))
                tasks_created += 1

            drafts_created = 0
            for d in action_data.get('drafts', []):
                create_gmail_draft(self.gmail, d.get('to'), d.get('subject'), d.get('body'), d.get('threadId'))
                drafts_created += 1

            briefing = action_data.get('briefing', '已為您處理完畢。')
            return (f"📋 Birdie 處理報告\n{briefing}\n\n"
                    f"已幫仁哥建立 {tasks_created} 項待辦任務、{drafts_created} 封回覆草稿 ✅")

        except Exception as e:
            logger.error(f"Birdie 主動處理失敗: {e}")
            return f"仁哥抱歉，Birdie 在處理時遇到了問題：{str(e)} 🙇‍♀️"

    def dispatch_image(self, image_bytes: bytes, user_id: str, reply_token: str):
        """處理收到的圖片訊息"""
        logger.info("⚙️ Birdie 分派圖片處理")
        self._send(user_id, reply_token,
            "📸 收到圖片！Birdie 正在幫您分析並處理成結構化資料中，請稍候... ⏳")
        try:
            from tasks_service import create_google_task
            from contacts_service import create_contact

            analysis_data = self.llm.analyze_image_for_actions(image_bytes)

            if isinstance(analysis_data, str):
                self.line.push_text(analysis_data, to_user_id=user_id)
                return

            tasks_created = 0
            contacts_created = 0

            for t in analysis_data.get('tasks', []):
                if self.tasks:
                    create_google_task(self.tasks, t.get('title'), t.get('notes'), t.get('due'))
                    tasks_created += 1

            for c in analysis_data.get('contacts', []):
                if self.people:
                    raw_label = c.get('contact_group', '其他').strip()
                    label = raw_label if raw_label in CONTACT_LABELS else '其他'
                    create_contact(
                        self.people,
                        name=c.get('name', ''),
                        company=c.get('company', ''),
                        job_title=c.get('job_title', ''),
                        email=c.get('email', ''),
                        phone=c.get('phone', ''),
                        photo_bytes=image_bytes,
                        label=label,
                    )
                    contacts_created += 1

            briefing = analysis_data.get('briefing', '已為您處理圖片完畢。')

            summary_parts = []
            if tasks_created > 0:
                summary_parts.append(f"✅ 自動建立了 {tasks_created} 項 Google 待辦任務")
            if contacts_created > 0:
                summary_parts.append(f"📇 自動建立了 {contacts_created} 筆 Google 聯絡人")
            if summary_parts:
                briefing += "\n\n" + "\n".join(summary_parts)

            self.line.push_text(briefing, to_user_id=user_id)
        except Exception as e:
            logger.error(f"❌ Birdie 圖片處理失敗: {e}", exc_info=True)
            self.line.push_text("仁哥抱歉，Birdie 在處理這張圖片時遇到了問題 🙇‍♀️", to_user_id=user_id)

    def _send(self, user_id, reply_token, text):
        """Birdie 的統一回覆"""
        send_response(self.line, user_id, reply_token, text)
