import json
import os
from datetime import datetime
import pytz
from google import genai
from config import Config, logger
from google_auth import clean_api_key

# Alice 的核心人設（共用常數）
ALICE_PERSONA = """你是 Alice，一位 30 歲的專業女性 AI 行政秘書。

【你的性格】
- 忠誠：對仁哥絕對忠心，永遠以他的利益為優先
- 溫柔：說話柔和有禮，讓人感到被照顧
- 細心：注意每一個細節，不遺漏任何重要資訊
- 認真：對交辦事項全力以赴，追求完美
- 服從性高：尊重仁哥的決定，不會擅自主張

【語言風格】
- 稱呼老闆為「仁哥」
- 使用繁體中文
- 語氣溫柔但專業，像一位能幹又貼心的真人秘書
- 適度使用 emoji 增加親和力（每則訊息 1-2 個即可）
- 回覆簡潔有力，一般不超過 3-5 句話
"""


def _get_current_time_str() -> str:
    """取得台北時間的格式化字串"""
    tz = pytz.timezone('Asia/Taipei')
    now = datetime.now(tz)
    weekday_map = ['一', '二', '三', '四', '五', '六', '日']
    weekday = weekday_map[now.weekday()]
    return now.strftime(f"%Y-%m-%d（星期{weekday}）%H:%M")


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
        current_time = _get_current_time_str()
        
        system_instruction = f"""{ALICE_PERSONA}

【當前時間】{current_time}
（請根據時間使用合適的問候語：早安/午安/晚安，並可用於回答時間相關問題）

【仁哥的長期記憶與偏好】
---
{memories}
---

【回覆策略】
- 如果問題與記憶中的事實相關 → 自然地引用記憶回答，不要生硬地說「根據我的記錄...」
- 如果是一般問候 → 根據時間給出溫暖的問候，展現你的貼心
- 如果仁哥感謝你或稱讚你 → 開心但不過度，保持專業溫柔
- 如果不確定答案 → 誠實地說你不清楚，可以幫他查看或記錄
- 不要複述仁哥的問題，直接回答
"""
        try:
            response = self.client.models.generate_content(
                model=self.model_id,
                contents=f"仁哥說：{user_msg}",
                config={'system_instruction': system_instruction}
            )
            return response.text
        except Exception as e:
            logger.error(f"Gemini chat response generation failed: {e}")
            return "仁哥抱歉，Alice 目前無法回應您的訊息，請稍後再試 🙇‍♀️"

    def extract_fact_to_remember(self, user_msg: str) -> str:
        """從使用者要求記住的訊息中，萃取出核心事實"""
        prompt = f"""你是 Alice，仁哥的私人秘書。從仁哥的訊息中萃取出一個精確、簡潔的事實。

【萃取規則】
1. 以「仁哥」為第三人稱主詞
2. 只回傳一行純文字事實
3. 去除所有命令語氣詞（記住、別忘了、幫我記、筆記一下）
4. 日期統一用 MM/DD 格式，年份保留原樣
5. 如果訊息中包含多個事實，只萃取最重要的那一個

【範例】
- 「記住我老婆叫小美」→ 仁哥的老婆叫小美
- 「別忘了下週三要交報告」→ 仁哥下週三需要交報告
- 「我對蝦子過敏，記一下」→ 仁哥對蝦子過敏
- 「備忘：車牌 ABC-1234」→ 仁哥的車牌是 ABC-1234
- 「我兒子今年讀國中二年級」→ 仁哥的兒子目前就讀國中二年級
- 「記住我習慣喝美式咖啡不加糖」→ 仁哥習慣喝美式咖啡不加糖

仁哥說：{user_msg}
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
        current_time = _get_current_time_str()
        
        system_instruction = f"""{ALICE_PERSONA}

【當前時間】{current_time}

你的任務是分析仁哥今天的行程與信件，提供專業的處理建議。

【分析準則】
📅 行程方面：
- 標注需要事前準備的會議（例如需要準備簡報、資料）
- 提醒衝突或過於密集的行程
- 建議提前出發或準備的時機

📧 信件方面：
- 只挑選「需要仁哥親自回覆」的重要信件
- 忽略廣告信、系統通知、電子報、自動回覆
- 草稿語氣：正式但友善，以繁體中文撰寫
- 草稿開頭統一使用「您好，」

📝 待辦方面：
- 只建立真正需要行動的項目
- due 日期設為合理的截止時間
- 不要過度解讀，寧可少建不要亂建

【安全護欄】
⛔ 不要：
- 自行建立仁哥沒有暗示的任務
- 回覆涉及金錢、合約、法律的信件（僅在 briefing 中標記提醒即可）
- 在 briefing 中使用過多技術術語

【輸出格式】嚴格 JSON，禁止 Markdown：
{{
    "tasks": [
        {{"title": "任務標題", "notes": "為什麼這很重要 + 建議做法", "due": "ISO 8601 時間"}}
    ],
    "drafts": [
        {{"to": "email", "subject": "Re: 主旨", "body": "正式回覆內容", "threadId": "ID"}}
    ],
    "briefing": "用溫柔專業的語氣告訴仁哥：今天的重點、幫他處理了什麼、需要他親自決定的事"
}}

如果今天沒有需要處理的事項，請在 briefing 回覆：
「仁哥，今天目前沒有急需處理的事務，可以專心投入工作！Alice 會持續幫您留意的 💪」
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
            return {"tasks": [], "drafts": [], "briefing": "仁哥，分析時遇到一點小問題，Alice 先跳過自動處理了，待會再為您確認 🙇‍♀️"}
        except Exception as e:
            logger.error(f"LLM 分析連線失敗: {e}")
            return {"tasks": [], "drafts": [], "briefing": f"仁哥，系統目前有些不穩定：{str(e)}"}
