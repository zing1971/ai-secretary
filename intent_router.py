import os
import json
import logging
from google import genai
from google_auth import clean_api_key

logger = logging.getLogger(__name__)


class IntentRouter:
    """雙層意圖分類器：規則前置 + LLM 後置"""

    # ===== 第一層：規則式快速匹配 =====
    RULE_PATTERNS = {
        "Query_Email":      ["信件", "郵件", "mail", "email", "寄件", "收件", "信箱", "inbox"],
        "Draft_Email":      ["回信", "回覆信件", "擬稿", "草擬回信", "草稿"],
        "Query_Calendar":   ["行程", "會議", "行事曆", "schedule", "calendar"],
        "Search_Drive":     ["檔案", "文件", "簡報", "drive", "雲端硬碟", "資料夾", "找檔"],
        "Memory_Update":    ["記住", "記下", "筆記", "存入記憶", "幫我記"],
        "Organize_Drive":   ["整理雲端", "整理硬碟", "整理 drive", "整理Drive"],
        "Proactive_Process": ["今日簡報", "今日簡報摘要", "每日簡報", "今天摘要", "日報"],
        "Search_Web":        ["上網搜尋", "上網查", "搜尋新聞", "查新聞"],
        "Query_Tasks":       ["待辦", "todo", "任務清單", "待辦事項"],
    }
    CHAT_PATTERNS = ["早安", "午安", "晚安", "謝謝", "你好", "嗨", "哈囉",
                     "感謝", "辛苦了", "掰掰", "晚安安", "安安"]

    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("請設定 GEMINI_API_KEY。")
        api_key = clean_api_key(api_key)
        self.client = genai.Client(api_key=api_key)

    def classify_intent(self, user_message: str) -> dict:
        """
        雙層意圖分類：
        1. 規則前置 — 關鍵字明確命中時直接返回（0ms，不消耗 tokens）
        2. LLM 後置 — 規則無法判定或多重命中時，由 LLM 精細分類
        """
        # 第一層：規則匹配
        rule_result = self._rule_based_classify(user_message)
        if rule_result:
            logger.info(f"⚡ 規則層命中: {rule_result['intent']}")
            return rule_result

        # 第二層：LLM 精細分類
        logger.info("🤖 規則層未命中，交由 LLM 分類")
        llm_result = self._llm_classify(user_message)

        # 歧義偵測：若 LLM 回傳了第二意圖 → 轉為 Clarify_Intent
        if llm_result.get("intent_secondary"):
            logger.info(f"🔀 偵測到歧義: {llm_result['intent']} vs {llm_result['intent_secondary']}")
            llm_result["original_intent"] = llm_result["intent"]
            llm_result["candidates"] = [
                llm_result["intent"],
                llm_result["intent_secondary"]
            ]
            llm_result["intent"] = "Clarify_Intent"

        return llm_result

    def _rule_based_classify(self, msg: str) -> dict | None:
        """
        規則式快速匹配。
        - 唯一命中 → 直接返回該意圖
        - 是問候閒聊 → Chat
        - 多重命中或無命中 → None（交給 LLM）
        """
        hits = {}
        for intent, keywords in self.RULE_PATTERNS.items():
            if any(kw in msg.lower() for kw in keywords):
                hits[intent] = True

        if len(hits) == 1:
            intent = list(hits.keys())[0]
            # 需要精細解析參數的意圖，強制送 LLM 以萃取關鍵字或時間範圍
            if intent in ["Draft_Email", "Query_Email", "Query_Calendar", "Search_Drive", "Search_Web", "Query_Project_Advisor"]:
                return None
            return {"intent": intent, "search_keyword": msg}

        if len(hits) == 0:
            # 純粹問候
            if any(kw in msg for kw in self.CHAT_PATTERNS):
                return {"intent": "Chat"}
            # 確認/取消（短回覆）
            if msg.strip() in {"好", "好的", "可以", "OK", "ok", "對", "是", "嗯",
                                "不要", "不用", "取消", "算了"}:
                return {"intent": "Confirm_Action" if msg.strip() in {"好", "好的", "可以", "OK", "ok", "對", "是", "嗯"} else "Cancel_Action"}

        return None  # 多重命中或無命中 → 交給 LLM

    def _llm_classify(self, user_message: str) -> dict:
        """LLM 精細分類（僅在規則無法判定時觸發）"""
        import datetime
        import pytz
        tz = pytz.timezone('Asia/Taipei')
        now = datetime.datetime.now(tz)
        weekday_map = ['一', '二', '三', '四', '五', '六', '日']
        current_time_str = now.strftime(f"%Y-%m-%d（星期{weekday_map[now.weekday()]}）%H:%M")

        # 未來 14 天日期對照表
        date_table = []
        for i in range(15):
            d = now + datetime.timedelta(days=i)
            wd = weekday_map[d.weekday()]
            date_table.append(f"offset {i} = {d.strftime('%Y-%m-%d')} (星期{wd})")
        date_mapping_str = "\n".join(date_table)

        system_instruction = f"""你是 Alice，一位專業的 AI 行政秘書。你服務的老闆叫「仁哥」。
你的任務是：將仁哥的 LINE 訊息精確媒合到對應的「意圖」。

⚠️ 規則：只能輸出單一 JSON 物件，禁止其他解釋性文字。

【當前時間及日期對應】
現在時間：{current_time_str}
{date_mapping_str}

【意圖分類】

1. "Query_Project_Advisor" — 詢問需要深度分析的專業領域知識（資安、IT、趨勢）。
   - 觸發條件：問題涉及「資安防護、漏洞分析、零信任、技術架構、攻擊手法、合規法規、AI趨勢」等需要專業文件支持的主題。
   - 必須輸出：`domain` ("infosec", "it", "trends") 與 `search_keyword`。

2. "Query_Calendar" — 查詢行程或會議安排。
   - 觸發條件：問題含有時間成份（明天、下週、幾號、幾點）且與行程相關。
   - 必須精確計算並輸出 `time_range` (start_offset, end_offset, label)。

3. "Query_Email" — 查詢或整理電子郵件。
   - 觸發條件：純查詢或整理信件，沒有要求「回信、擬稿」。
   - 例如：「幫我找OO的信」、「摘要最新信件」。
   - 輸出 `search_keyword` 與 `time_range`。

4. "Draft_Email" — 擬寫回信或草稿。
   - 觸發條件：明確要求「回信、擬寫、草擬回信、答覆」。
   - 例如：「幫我回信給OO說明天會到」、「檢查信件並幫我草擬回覆」。
   - 輸出 `search_keyword`（找哪封信來回）與 `draft_instruction`（回覆的具體指示）。

5. "Search_Drive" — 搜尋雲端硬碟檔案。
   - 觸發條件：問題明確涉及「檔案、文件、簡報、資料夾、雲端」。
   - 必須輸出 `search_keyword`。

5. "Confirm_Action" / "Cancel_Action" — 確認或取消動作。

6. "Memory_Update" — 要求記住某事。

7. "Organize_Drive" — 要求整理雲端硬碟。

8. "Proactive_Process" — 今日綜合簡報。

9. "Search_Web" — 詢問即時性資訊。
   - 觸發條件：需要最新的外部資訊（天氣、股價、新聞、即時事件）。
   - 必須輸出 `search_keyword`。

10. "Chat" — 純粹的問候閒聊（早安、感謝、問好）。

🔑 核心判斷規則：

❶ 如果問題「同時可能歸屬多個資料來源」（例如：可能是知識庫也可能是網路搜尋）
   → intent 填最可能的，intent_secondary 填第二可能的，ambiguity_reason 填原因。
❷ 如果問題只有一個明確的歸屬 → intent_secondary 填 null。
❸ 純粹問候閒聊 → Chat，intent_secondary 填 null。
❹ 當無法確定查詢目標時 → 必須填寫 intent_secondary，絕不能猜測。

📤 JSON 輸出格式：
{{
  "intent": "最可能的意圖",
  "intent_secondary": "第二可能的意圖（無歧義時填 null）",
  "ambiguity_reason": "歧義原因（無歧義時填 null）",
  "domain": "infosec/it/trends（僅 Query_Project_Advisor 時）",
  "search_keyword": "搜尋關鍵字",
  "draft_instruction": "擬寫信件的具體指示(無則填null)",
  "time_range": {{"start_offset": 0, "end_offset": 0, "label": "今天"}}
}}
"""
        try:
            response = self.client.models.generate_content(
                model='gemini-2.0-flash',
                contents=f"仁哥傳來的訊息：「{user_message}」\n請輸出 JSON 意圖分析。",
                config={
                    'system_instruction': system_instruction,
                    'response_mime_type': 'application/json'
                }
            )

            result = json.loads(response.text)
            logger.info(f"🤖 LLM 分類結果: intent={result.get('intent')}, "
                        f"secondary={result.get('intent_secondary')}")
            return result

        except Exception as e:
            logger.error(f"意圖分析失敗: {e}")
            return {"intent": "Chat"}
