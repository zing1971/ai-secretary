"""
歧義澄清與確認/取消流程處理

從 ActionDispatcher 抽取的共用流程控制邏輯。
由 RoleDispatcher 在分流前進行攔截處理。
"""
import time
import logging

logger = logging.getLogger(__name__)

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

# 確認/取消動作的關鍵字
CONFIRM_KEYWORDS = {"好", "好的", "可以", "執行", "同意", "沒問題", "ok", "OK", "去做吧", "做吧", "對", "是", "嗯"}
CANCEL_KEYWORDS = {"不要", "不用", "取消", "算了", "停", "不", "別", "放棄"}


class ClarifyHandler:
    """處理歧義澄清流程（暫存查詢 → 呈現選項 → 攔截回覆）"""

    def __init__(self):
        self._pending_clarification = {}

    def handle_clarify(self, intent_data, user_msg, user_id, reply_token, send_fn):
        """處理 Clarify_Intent：暫存原始查詢並傳送選項給使用者"""
        candidates = intent_data.get("candidates", [])

        self._pending_clarification[user_id] = {
            "original_query": user_msg,
            "original_intent_data": intent_data,
            "candidates": candidates,
            "timestamp": time.time()
        }

        # 組合選項訊息
        options = []
        for num, intent_key in INTENT_MENU.items():
            emoji, label = INTENT_LABELS.get(intent_key, ("❓", "其他"))
            options.append(f"{num}️⃣ {emoji} {label}")

        ambiguity = intent_data.get("ambiguity_reason", "")
        reason_text = f"\n（{ambiguity}）" if ambiguity else ""

        msg = (
            f"仁哥，關於「{user_msg}」，{reason_text}\n"
            f"請問您想從哪裡查詢呢？😊\n\n"
            + "\n".join(options) +
            "\n\n直接回覆數字就好 ✨"
        )
        send_fn(user_id, reply_token, msg)

    def try_intercept_choice(self, user_msg, user_id, reply_token, send_fn, dispatch_fn):
        """
        嘗試攔截數字快捷選擇。
        返回 True 表示已攔截處理，False 表示非澄清流程。
        """
        if user_msg.strip() not in ["1", "2", "3", "4"]:
            return False

        choice = int(user_msg.strip())
        pending = self._pending_clarification.get(user_id)
        if not pending:
            return False

        # 過期檢查（5 分鐘）
        if time.time() - pending["timestamp"] > 300:
            del self._pending_clarification[user_id]
            send_fn(user_id, reply_token,
                "仁哥，這個查詢已經超過 5 分鐘了 ⏰\n"
                "麻煩您重新提問一次好嗎？")
            return True

        target_intent = INTENT_MENU.get(choice)
        if not target_intent:
            return False

        original_query = pending["original_query"]
        original_data = pending.get("original_intent_data", {})
        del self._pending_clarification[user_id]

        # 回覆確認
        emoji, label = INTENT_LABELS.get(target_intent, ("", ""))
        send_fn(user_id, reply_token,
            f"✅ 收到！正在從「{label}」查詢「{original_query}」... ⏳")

        # 重組 intent_data 並轉發
        original_data["intent"] = target_intent
        original_data["search_keyword"] = original_data.get("search_keyword", original_query)
        if target_intent == "Query_Project_Advisor" and not original_data.get("domain"):
            original_data["domain"] = "it"

        logger.info(f"🔄 澄清轉發: {target_intent} | 查詢: {original_query}")
        dispatch_fn(original_data, original_query, user_id, reply_token=None)
        return True
