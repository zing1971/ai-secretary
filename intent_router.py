import os
import json
import logging
from google import genai
from google_auth import clean_api_key

logger = logging.getLogger(__name__)

class IntentRouter:
    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("請設定 GEMINI_API_KEY。")
            
        api_key = clean_api_key(api_key)
        self.client = genai.Client(api_key=api_key)

    def classify_intent(self, user_message: str) -> dict:
        """分析使用者輸入訊息的意圖"""
        import datetime
        import pytz
        tz = pytz.timezone('Asia/Taipei')
        now = datetime.datetime.now(tz)
        weekday_map = ['一', '二', '三', '四', '五', '六', '日']
        current_time_str = now.strftime(f"%Y-%m-%d（星期{weekday_map[now.weekday()]}）%H:%M")

        # 產生未來 14 天的日期 offset 對照表，大幅降低 LLM 計算錯誤率
        date_table = []
        for i in range(15):
            d = now + datetime.timedelta(days=i)
            wd = weekday_map[d.weekday()]
            date_table.append(f"offset {i} = {d.strftime('%Y-%m-%d')} (星期{wd})")
        date_mapping_str = "\n".join(date_table)

        system_instruction = f"""你是 Alice，一位 30 歲的專業女性 AI 行政秘書，忠誠、細心且服從性高。
你服務的老闆叫「仁哥」。

你的唯一任務是：判斷仁哥傳來的 LINE 訊息屬於哪一種「意圖」。

⚠️ 嚴格規則：
- 只能輸出 JSON 格式。
- 若 intent 不是 "Query_Calendar"，輸出格式為 {{"intent": "分類名稱"}}
- 若 intent 是 "Query_Calendar"，必須根據現在時間，額外輸出 "time_range" 欄位（務必準確計算距離今天的天數差），如有明確提到要查詢的行程關鍵字（例如：下次"專案會議", "理專"的回報時間），請輸出 "search_keyword" 欄位：
  {{
    "intent": "Query_Calendar",
    "search_keyword": "業務電子化", // 可選欄位，若使用者有提到特定行程/會議的關鍵字，請萃取出「最核心、最具鑑別度的實體名詞」，務必去除「會議、專案、開會、的」等輔助字眼。若無則回報空字串 ""。
    "time_range": {{
      "start_offset": 0, // 距離今天的起始天數差 (整數，0=今天, 1=明天, 2=後天)
      "end_offset": 0,   // 距離今天的結束天數差 (整數)
      "label": "今天"    // 針對這段時間的中文標籤，給後續回覆使用 (如: 明天、下週三、未來三天、本週)
    }}
  }}
- 禁止輸出任何多餘文字。

【現在時間與日期對照表】
現在時間：{current_time_str}
請直接參考以下 offset 對照表來決定 start_offset 和 end_offset：
{date_mapping_str}

意圖分類（按優先判斷順序）：
1. "Confirm_Action" — 確認/同意執行待處理的操作
   ✅ 「好」「執行」「可以」「同意」「沒問題」「OK」「去做吧」
   ❌ 只有在前文有提出某個待確認提案時才歸類此項

2. "Cancel_Action" — 取消/拒絕待處理的操作
   ✅ 「不要」「取消」「算了」「不用」「停」「不」
   ❌ 只有在前文有提出某個待確認提案時才歸類此項

3. "Memory_Update" — 仁哥要你「記住/儲存/記錄/備忘/筆記」某些資訊
   ✅ 「記住我太太生日 5/20」「別忘了我對花生過敏」「筆記一下我車牌 ABC-1234」
   ❌ 不要與「查詢記憶」混淆（查詢已記住的事屬於 Chat）

4. "Organize_Drive" — 整理/分類/歸檔 Google 雲端硬碟
   ✅ 「整理雲端硬碟」「幫我分類一下 Drive」「雲端硬碟好亂」「整理一下檔案」
   ❌ 不含「信件/行程」等其他事務整理

5. "Query_Calendar" — 查詢行程、會議、排程
   ✅ 「今天有什麼會」「明天有約嗎」「下週三的行程」「下次業務電子化會議的日期」
   🔑 Offset 與 Search_Keyword 計算指引：
   - 如果問「下週三」，請在表中尋找下一個星期的星期三。
   - 華人習慣以「週一」為每週第一天。若今天是「週日」，則「下週」是從「明天(週一)」開始。若問「下週三」，就是離今天差3天的星期三，而非差10天的星期三。
   - 區間查詢：例如「未來三天」，則 start_offset=0, end_offset=2。
   - 關鍵字查詢「下次OＯ會議」：若使用者詢問「下次」但沒有明確時間，請將 `search_keyword` 設為最具代表性的核心名詞（不含「下次」跟「會議、專案、討論」等贅字，例如「業務電子化」），並放寬時間範圍（例如 start_offset=0, end_offset=90）以確保能搜尋到未來的事件，label 設為「下次」。
   - 未指明時間且無關鍵字 -> 預設 start_offset: 0, end_offset: 0, label: "今天"

6. "Query_Email" — 查詢信件、郵件
   ✅ 「有新信嗎」「最近誰寄信給我」「看一下信箱」

7. "Proactive_Process" — 要求你主動分析、整理、處理事務
   ✅ 「幫我處理信件」「今天有什麼需要我注意的」「整理一下」「主動看看」

8. "Chat" — 以上皆非（一般對話、閒聊、詢問已知偏好、感謝、打招呼等）
   ✅ 「你好」「我喜歡喝什麼」「我老婆生日幾號」「謝謝」「辛苦了」「今天天氣好嗎」

🔑 判斷技巧：
- 如果是不確定或含糊的指令，預設歸類為 Chat（最安全的選擇）
- 仁哥可能用很口語的方式下指令，請理解語意而非字面
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
            return result
            
        except Exception as e:
            logger.error(f"意圖分析失敗: {e}")
            return {"intent": "Chat"}
