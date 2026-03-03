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

        # 產生未來 14 天的日期 offset 對照表
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

意圖分類（由高至低順位）：

1. "Query_Project_Advisor" — 詢問專業領域知識（資安、IT、趨勢）。
   - 關鍵字特徵：勒索軟體、零信任、漏洞、AI、雲端、趨勢、建議、攻擊分析、技術架構。
   - 必須輸出：`domain` ("infosec", "it", "trends") 與 `search_keyword`。
   - 範例：「查一下勒索軟體的建議」-> {{"intent": "Query_Project_Advisor", "domain": "infosec", "search_keyword": "勒索軟體"}}

2. "Query_Calendar" / "Query_Email" — 查詢行程或電子郵件。
   - 必須精確計算並輸出 `time_range` (start_offset, end_offset, label)。
   - 若為信件擬稿，歸類為 `Query_Email`。

3. "Search_Drive" — 關鍵字搜尋雲端硬碟檔案（必須輸出 `search_keyword`）。

4. "Confirm_Action" / "Cancel_Action" — 針對 Alice 的提案回答「好」、「可以」或「不用」、「取消」。

5. "Memory_Update" — 老闆要求「記住」或「存入筆記」某事。

6. "Organize_Drive" — 要求進行雲端硬碟分類整理。

7. "Proactive_Process" — 今日綜合簡報。

8. "Chat" — 一般閒聊、感恩、問好，或詢問 Alice 記住了什麼（查詢核心記憶）。

🔑 輸出導引：
- 若使用者輸入「資安建議」、「趨勢分析」等專業需求，請務必歸類為 Query_Project_Advisor。
- 若無法判定，請回傳 Chat。
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
