"""
角色分流器 — RoleDispatcher

取代舊版 ActionDispatcher 的巨型 if-elif 鏈。
根據意圖類型自動將訊息分配給 Alice（查詢）或 Birdie（執行）。

架構：
  使用者訊息 → IntentRouter → RoleDispatcher
                                  ├── ClarifyHandler（歧義攔截）
                                  ├── Alice（查詢/檢索/閒聊）
                                  └── Birdie（執行/變更/排程）

支援 TelegramService 與 LineService（相容介面），不需明確引入即可互換。
"""
import logging

from alice.query_handler import AliceQueryHandler
from birdie.action_handler import BirdieActionHandler
from shared.clarify_handler import ClarifyHandler
from shared.line_responder import send_response

from llm_service import LLMService
from memory_service import MemoryService
from pinecone_memory import PineconeMemory
from drive_service import DriveService
from drive_organizer import DriveOrganizer
from notebooklm_service import NotebookLMService

logger = logging.getLogger(__name__)


class RoleDispatcher:
    """
    雙角色分流核心。

    初始化時建立 Alice 與 Birdie 兩個角色 Handler，
    dispatch() 方法根據意圖自動選擇角色處理。

    messaging_service 接受 TelegramService 或 LineService（相容介面）。
    """

    def __init__(self, messaging_service, llm_service: LLMService,
                 gmail, calendar, tasks, sheets, drive=None, people=None, creds=None):
        self.line = messaging_service  # 保留屬性名稱以相容 Alice/Birdie 內部呼叫
        self.llm = llm_service
        self.creds = creds

        # 初始化 NotebookLM 與記憶服務（共用）
        notebooklm = NotebookLMService()
        pinecone_mem = PineconeMemory()
        self.memory = MemoryService(sheets, llm_service, pinecone_mem)

        # 初始化 Drive 服務
        drive_svc = None
        drive_organizer = None
        if drive:
            drive_svc = DriveService(drive)
            drive_organizer = DriveOrganizer(drive_svc, llm_service)
            logger.info("✅ Drive 整理代理就緒")
        else:
            logger.warning("⚠️ Drive 服務未就緒，整理功能停用")

        # ===== 建立雙角色 =====
        self.alice = AliceQueryHandler(
            messaging_service=messaging_service,
            llm_service=llm_service,
            gmail=gmail,
            calendar=calendar,
            tasks=tasks,
            memory_service=self.memory,
            notebooklm_service=notebooklm,
            drive_service_wrapper=drive_svc,
            creds=creds
        )

        self.birdie = BirdieActionHandler(
            messaging_service=messaging_service,
            llm_service=llm_service,
            gmail=gmail,
            calendar=calendar,
            tasks=tasks,
            sheets=sheets,
            memory_service=self.memory,
            drive_organizer=drive_organizer,
            people=people,
            creds=creds
        )

        # ===== 共用流程控制 =====
        self.clarify = ClarifyHandler()

        # 保留對 drive_organizer 的引用（app.py 需要）
        self.drive_organizer = drive_organizer

        # ===== 跨輪次對話上下文暫存 =====
        self._user_email_context = {}

        # ===== 跨角色協作：Alice → Birdie 轉交回呼 =====
        self.alice.set_handoff(self._handoff_to_birdie)

        logger.info("🎭 雙角色架構就緒：🔍 Alice（情報秘書）+ ⚙️ Birdie（執行管家）")

    def _handoff_to_birdie(self, intent_data, user_msg, user_id, reply_token):
        """跨角色轉交：Alice → Birdie"""
        intent = intent_data.get("intent", "")
        logger.info(f"🔄 跨角色轉交 Alice→Birdie: {intent}")
        self.birdie.dispatch(intent_data, user_msg, user_id, reply_token)

    def dispatch(self, intent_data, user_msg: str, user_id: str, reply_token: str = None):
        """根據意圖分流給 Alice 或 Birdie"""

        if isinstance(intent_data, str):
            intent = intent_data
        else:
            intent = intent_data.get("intent", "Chat")

        logger.info(f"🎭 分流意圖: {intent}")

        # ⚡ 前置攔截 1：數字快捷選擇（歧義澄清）
        if self.clarify.try_intercept_choice(
            user_msg, user_id, reply_token,
            send_fn=self._send,
            dispatch_fn=self.dispatch  # 遞迴回 dispatch
        ):
            return

        # ⚡ 前置攔截 2：Birdie 有待確認提案時，短回覆直接攔截
        override_intent = self.birdie.try_intercept_confirm_cancel(user_msg, user_id, reply_token)
        if override_intent:
            intent = override_intent
            if isinstance(intent_data, dict):
                intent_data["intent"] = override_intent

        # ===== 跨輪對話上下文機制 =====
        if intent == "Query_Email":
            if isinstance(intent_data, dict):
                self._user_email_context[user_id] = intent_data.get("search_keyword", "")
        elif intent == "Draft_Email":
            if isinstance(intent_data, dict) and not intent_data.get("search_keyword"):
                intent_data["search_keyword"] = self._user_email_context.get(user_id, "")
                # 將原始訊息視為草擬指示
                intent_data["draft_instruction"] = intent_data.get("draft_instruction", user_msg)

        # ===== 歧義處理 =====
        if intent == "Clarify_Intent":
            self.clarify.handle_clarify(
                intent_data, user_msg, user_id, reply_token,
                send_fn=self._send
            )
            return

        # ===== 角色分流 =====
        if self.alice.can_handle(intent):
            self.alice.dispatch(intent_data, user_msg, user_id, reply_token)
        elif self.birdie.can_handle(intent):
            self.birdie.dispatch(intent_data, user_msg, user_id, reply_token)
        else:
            # 未知意圖 → 降級為 Alice 閒聊
            logger.warning(f"⚠️ 未知意圖 '{intent}'，降級為 Alice Chat")
            self.alice.dispatch("Chat", user_msg, user_id, reply_token)

    def dispatch_image(self, image_bytes: bytes, user_id: str, reply_token: str):
        """圖片處理統一交由 Birdie"""
        self.birdie.dispatch_image(image_bytes, user_id, reply_token)

    def handle_proactive_process(self) -> str:
        """每日簡報統一交由 Birdie"""
        return self.birdie.handle_proactive_process()

    def _send(self, user_id, reply_token, text):
        """統一回覆"""
        send_response(self.line, user_id, reply_token, text)
