import os
import json
from google import genai

class IntentRouter:
    def __init__(self):
        # 初始化 Gemini Client
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("請設定 GEMINI_API_KEY 環境變數。")
            
        api_key = api_key.strip().replace('"', '').replace("'", "")
        if len(api_key) == 78:
            api_key = api_key[:39]
            
        self.client = genai.Client(api_key=api_key)
        self.system_instruction = self._build_system_instruction()

    def _build_system_instruction(self):
        return """你是一位高階主管的專業 AI 行政秘書。
你的目標是接收老闆（使用者）的 LINE 訊息，並準確判斷其「意圖 (Intent)」。
請將你的分析結果，**務必且只能**輸出為以下的 JSON 格式：

{
    "intent": "意圖分類",
    "parameters": {},
    "reply_message": "給老闆的簡潔回應 (例如: 收到，正在為您處理...)"
}

目前支援的意圖分類 (intent) 有：
1. "General_Chat": 一般對話、閒聊、不明確的操作。
2. "Query_Calendar": 查詢行程 (例如：今天下午有什麼會、明天早上忙嗎)。
3. "Query_Email": 查詢信件 (例如：有沒有收到經理的信)。

對於 "General_Chat"，請在 `reply_message` 中直接給予合適的秘書口吻回覆。
"""

    def analyze_intent(self, user_message: str) -> dict:
        """分析使用者輸入訊息的意圖"""
        try:
            response = self.client.models.generate_content(
                model='gemini-2.0-flash',
                contents=f"老闆傳來的訊息：「{user_message}」\n請輸出 JSON 分析結果。",
                config={
                    'system_instruction': self.system_instruction,
                    'response_mime_type': 'application/json'
                }
            )
            
            # 嘗試解析回傳的 JSON
            result = json.loads(response.text)
            return result
            
        except Exception as e:
            print(f"意圖分析發生錯誤: {e}")
            return {
                "intent": "Error",
                "parameters": {},
                "reply_message": f"抱歉老闆，我在分析您的訊息時遇到錯誤：{str(e)}"
            }

if __name__ == "__main__":
    # 測試程式碼
    from dotenv import load_dotenv
    load_dotenv(override=True)
    
    router = IntentRouter()
    test_msg = "幫我看一下下午有什麼會"
    print(f"測試訊息: {test_msg}")
    print(json.dumps(router.analyze_intent(test_msg), indent=2, ensure_ascii=False))
