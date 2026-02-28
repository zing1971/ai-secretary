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
        system_instruction = """你是一位高階主管的專業 AI 行政秘書。
你的目標是接收老闆（使用者）的 LINE 訊息，並準確判斷其「意圖 (Intent)」。

請將你的分析結果，**務必且只能**輸出為以下的 JSON 格式：
{
    "intent": "意圖分類"
}

目前支援的意圖分類 (intent) 有：
1. "Chat": 一般問候、對話、或是詢問「關於老闆個人偏好、已記住的事實」。例如：「你好」、「你是誰」、「我老婆生日幾號？」、「我喜歡喝什麼？」。
2. "Memory_Update": 當老闆要求你「記住」、「儲存」、「記錄」某些個人資訊時。例如：「記住我老婆生日是 5/20」、「記錄我有咖啡因過敏」。
3. "Query_Calendar": 查詢行程。例如：「今天下午有什麼會」、「明天忙嗎」。
4. "Query_Email": 查詢信件。例如：「有新信嗎」。
5. "Proactive_Process": 請求主動分析與處理。例如：「幫我處理今天的信件」、「主動看看」。
"""
        try:
            response = self.client.models.generate_content(
                model='gemini-2.0-flash',
                contents=f"老闆傳來的訊息：「{user_message}」\n請輸出 JSON 意圖分析。",
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
