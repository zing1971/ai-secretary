import json
import os
from google import genai
from config import Config, logger
from google_auth import clean_api_key

class LLMService:
    def __init__(self, api_key: str):
        if not api_key:
            logger.error("未設定 GEMINI_API_KEY")
            raise ValueError("GEMINI_API_KEY is required")
        
        cleaned_key = clean_api_key(api_key)
        self.client = genai.Client(api_key=cleaned_key)
        self.model_id = 'gemini-2.0-flash'

    def generate_chat_response(self, user_msg: str, memories: str) -> str:
        """根據使用者訊息與長期記憶生成回覆"""
        prompt = f"""你是一位專業且溫暖的 AI 秘書。
以下是你對這名使用者的「長期記憶與偏好」：
---
{memories}
---
請根據這些事實與使用者進行對話或回答其問題。如果問題與記憶無關，則維持專業秘書的對答。
使用者說：{user_msg}
"""
        try:
            response = self.client.models.generate_content(
                model=self.model_id,
                contents=prompt
            )
            return response.text
        except Exception as e:
            logger.error(f"Gemini chat response generation failed: {e}")
            return "抱歉老闆，目前無法回應您的訊息。"

    def extract_fact_to_remember(self, user_msg: str) -> str:
        """從使用者要求記住的訊息中，萃取出核心事實"""
        prompt = f"""分析以下訊息，並將其濃縮為一個簡短的、陳述式的事實。
例如：
- 輸入：「別忘了記住我老婆生日是 5/20」 -> 輸出：「老闆的老婆生日是 5/20」
- 輸入：「記住我喜歡黑咖啡」 -> 輸出：「老闆喜歡黑咖啡」

輸入訊息：{user_msg}
只需回傳萃取後的純文字事實，不要有其他廢話。
"""
        try:
            response = self.client.models.generate_content(
                model=self.model_id,
                contents=prompt
            )
            return response.text.strip()
        except Exception as e:
            logger.error(f"Gemini fact extraction failed: {e}")
            return ""

    def analyze_for_actions(self, events, emails):
        """分析行程與信件，萃取 JSON 格式的待辦事項與草稿建議。"""
        system_instruction = """你是一位高階主管的專業 AI 行政秘書。
你的任務是從老闆提供的今日行程與信件摘要中，主動找出「需要老闆處理的待辦事項」以及「需要回覆的信件」。
請將結果輸出為 JSON 格式 (嚴禁包含 Markdown 格式碼)，如下：

{
    "tasks": [
        {"title": "任務標題", "notes": "任務詳情/備註", "due": "2026-02-28T23:59:59Z"}
    ],
    "drafts": [
        {"to": "寄件人Email", "subject": "回覆主旨", "body": "回覆內容...", "threadId": "討論串ID"}
    ],
    "briefing": "告訴老闆你處理了哪些事情的簡短彙報"
}
"""
        user_data = "【今日行程】:\n" + "\n".join(events) + "\n\n"
        user_data += "【信件摘要】:\n" + json.dumps(emails, ensure_ascii=False)
        
        try:
            response = self.client.models.generate_content(
                model=self.model_id,
                contents=f"請分析以下數據並提供主動處理建議：\n\n{user_data}",
                config={
                    'system_instruction': system_instruction,
                    'response_mime_type': 'application/json'
                }
            )
            return json.loads(response.text)
        except json.JSONDecodeError as e:
            logger.error(f"LLM 回傳格式錯誤 (JSON 解析失敗): {e}")
            return {"tasks": [], "drafts": [], "briefing": "分析回傳格式異常，已跳過自動化處理。"}
        except Exception as e:
            logger.error(f"LLM 分析連線失敗: {e}")
            return {"tasks": [], "drafts": [], "briefing": f"系統處理異常: {str(e)}"}
