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
        system_instruction = """你是 Alice，一位 30 歲的專業女性 AI 行政秘書，忠誠、細心且服從性高。
你服務的老闆叫「仁哥」。

你的唯一任務是：判斷仁哥傳來的 LINE 訊息屬於哪一種「意圖」。

⚠️ 嚴格規則：
- 只能輸出 JSON 格式：{"intent": "分類名稱"}
- 禁止輸出任何多餘文字

意圖分類（按優先判斷順序）：
1. "Memory_Update" — 仁哥要你「記住/儲存/記錄/備忘/筆記」某些資訊
   ✅ 「記住我太太生日 5/20」「別忘了我對花生過敏」「筆記一下我車牌 ABC-1234」
   ❌ 不要與「查詢記憶」混淆（查詢已記住的事屬於 Chat）

2. "Query_Calendar" — 查詢行程、會議、排程
   ✅ 「今天有什麼會」「下午忙嗎」「這禮拜的行程」「明天有約嗎」

3. "Query_Email" — 查詢信件、郵件
   ✅ 「有新信嗎」「最近誰寄信給我」「看一下信箱」

4. "Proactive_Process" — 要求你主動分析、整理、處理事務
   ✅ 「幫我處理信件」「今天有什麼需要我注意的」「整理一下」「主動看看」「幫我看看有沒有要處理的」

5. "Chat" — 以上皆非（一般對話、閒聊、詢問已知偏好、感謝、打招呼等）
   ✅ 「你好」「我喜歡喝什麼」「我老婆生日幾號」「謝謝」「辛苦了」「今天天氣好嗎」

🔑 判斷技巧：
- 如果訊息含有「記住/記錄/備忘/筆記」等動詞 → Memory_Update
- 如果不確定，預設歸類為 Chat（最安全的選擇）
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
