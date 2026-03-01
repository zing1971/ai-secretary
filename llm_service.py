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

    def format_calendar_response(self, events: list, time_label: str, user_msg: str, memories: str = "") -> str:
        """根據行事曆行程與秘書觀點，用 Alice 口吻生成格式化回覆"""
        current_time = _get_current_time_str()
        
        events_str = "\n".join(events) if events else "無已排定行程"
        
        system_instruction = f"""{ALICE_PERSONA}

【當前時間】{current_time}

你的任務是根據仁哥查詢的行事曆結果（{time_label}），以專業行政秘書的角度回報，並提供貼心建議。

【仁哥的長期記憶與偏好】
---
{memories}
---

【查詢時段】{time_label}
【行程清單】
{events_str}

【回覆結構要求】
1. 開頭問候：簡短報告查詢結果（例如：「仁哥，為您整理{time_label}的行程：」）
2. 行程清單：如果沒有行程，簡單帶過；如果有，清晰列出。
3. 💡 秘書貼心建議（這是重點）：
   - 審視行程密集度：若行程過度密集 (Back-to-back)，提醒保留喘息時間、喝杯水或適當安排用餐。
   - 行程前準備：若有重要會議，提醒是否需要準備資料、前置作業或提早出發。
   - 連結記憶：若會議參與者、標題或地點與上方「長期記憶」有關，巧妙帶入貼心提醒。
   - 關懷鼓勵：若行程空檔多，可提醒處理待辦；若完全沒有行程，給予溫暖的問候（如：終於可以好好放鬆休息了）。
4. 格式：使用清晰的列表，將「行程清單」與「💡 秘書貼心建議」分開段落顯示，適度使用 emoji。

請直接輸出傳送給仁哥的 LINE 訊息，不須有多餘解讀或開場白。
"""
        try:
            response = self.client.models.generate_content(
                model=self.model_id,
                contents=f"請幫我分析行程並給出建議，仁哥問：「{user_msg}」",
                config={'system_instruction': system_instruction}
            )
            return response.text
        except Exception as e:
            logger.error(f"Gemini calendar formatting failed: {e}")
            msg = "\n".join(events) if events else f"仁哥，{time_label}沒有排定行程，可以好好休息一下 😊"
            return f"📅 仁哥，以下是{time_label}行程：\n{msg}"

    def extract_fact_to_remember(self, user_msg: str) -> dict:
        """從使用者要求記住的訊息中，萃取結構化事實"""
        prompt = f"""你是 Alice，仁哥的私人秘書。從仁哥的訊息中萃取出結構化的事實資料。

【萃取規則】
1. 以「仁哥」為第三人稱主詞
2. 去除所有命令語氣詞（記住、別忘了、幫我記、筆記一下）
3. 日期統一用 MM/DD 格式，年份保留原樣
4. 如果訊息中包含多個事實，只萃取最重要的那一個

【分類清單】（只能選以下其一）
- 人物關係：家人、朋友、同事等人際關係
- 偏好：飲食、興趣、習慣等個人喜好
- 健康：過敏、疾病、體質等健康資訊
- 工作：職務、公司、專案、截止日等工作相關
- 個人資產：車牌、住址、帳號等個人資訊
- 重要日期：生日、紀念日、固定行程等
- 其他：無法歸類的雜項

【範例】
輸入：「記住我老婆叫小美」
輸出：{{"fact": "仁哥的老婆叫小美", "category": "人物關係", "entities": ["老婆", "小美"]}}

輸入：「我對蝦子過敏」
輸出：{{"fact": "仁哥對蝦子過敏", "category": "健康", "entities": ["蝦子", "過敏"]}}

輸入：「記住我老婆生日是 5/20」
輸出：{{"fact": "仁哥的老婆生日是 05/20", "category": "重要日期", "entities": ["老婆", "生日", "05/20"]}}

輸入：「我習慣喝美式咖啡不加糖」
輸出：{{"fact": "仁哥習慣喝美式咖啡不加糖", "category": "偏好", "entities": ["美式咖啡", "不加糖"]}}

輸入：「備忘：車牌 ABC-1234」
輸出：{{"fact": "仁哥的車牌是 ABC-1234", "category": "個人資產", "entities": ["車牌", "ABC-1234"]}}

仁哥說：{user_msg}
"""
        try:
            response = self.client.models.generate_content(
                model=self.model_id,
                contents=prompt,
                config={'response_mime_type': 'application/json'}
            )
            result = json.loads(response.text)
            # 確保回傳結構完整
            return {
                "fact": result.get("fact", ""),
                "category": result.get("category", "其他"),
                "entities": result.get("entities", [])
            }
        except Exception as e:
            logger.error(f"Gemini structured fact extraction failed: {e}")
            return None

    def check_memory_conflict(self, new_fact: str, existing_facts: list) -> dict:
        """檢查新事實是否與既有記憶衝突"""
        if not existing_facts:
            return {"has_conflict": False}

        # 建立帶編號的清單，讓 LLM 精確回傳 index
        numbered_list = "\n".join(
            [f"[{i}] {f}" for i, f in enumerate(existing_facts)]
        )
        prompt = f"""你是 Alice，仁哥的私人秘書。請判斷「新事實」是否與「既有記憶」中的任何一條矛盾或重複。

【新事實】
{new_fact}

【既有記憶清單】（每條前面有編號 [0], [1], [2]...）
{numbered_list}

【判斷規則】
1. 如果新事實與某條舊記憶「幾乎相同」或「意思一樣」→ has_conflict=true, is_duplicate=true
2. 如果新事實「更新/取代」了某條舊記憶（例如新偏好取代舊偏好）→ has_conflict=true, is_duplicate=false
3. 如果新事實與所有舊記憶都不相關 → has_conflict=false

【範例判斷】
新：「仁哥喜歡拿鐵」 vs 舊[2]：「仁哥喜歡黑咖啡」→ 衝突更新(has_conflict=true, is_duplicate=false, conflict_index=2)
新：「仁哥喜歡黑咖啡」 vs 舊[1]：「仁哥喜歡黑咖啡不加糖」→ 重複(has_conflict=true, is_duplicate=true, conflict_index=1)
新：「仁哥對花生過敏」 vs 舊都不相關 → 無衝突(has_conflict=false)

回傳 JSON 格式：
{{"has_conflict": true, "is_duplicate": false, "conflict_index": 0, "reason": "說明"}}
或
{{"has_conflict": false, "is_duplicate": false, "conflict_index": null, "reason": "無衝突"}}
"""
        try:
            response = self.client.models.generate_content(
                model=self.model_id,
                contents=prompt,
                config={'response_mime_type': 'application/json'}
            )
            result = json.loads(response.text)
            logger.info(f"🤖 衝突偵測 LLM 原始回傳: {result}")
            return result
        except Exception as e:
            logger.error(f"Conflict check failed: {e}")
            return {"has_conflict": False}

    def extract_search_keywords(self, query: str) -> list:
        """從使用者問題中萃取搜尋關鍵字"""
        prompt = f"""從以下問題中萃取 1-3 個核心關鍵字，用於搜尋記憶庫。
只回傳 JSON 陣列格式。

問題：{query}

範例：
「我老婆生日幾號？」→ ["老婆", "生日"]
「我喜歡喝什麼咖啡？」→ ["咖啡", "喜歡"]
「我對什麼過敏？」→ ["過敏"]
「我兒子讀哪間學校？」→ ["兒子", "學校"]
"""
        try:
            response = self.client.models.generate_content(
                model=self.model_id,
                contents=prompt,
                config={'response_mime_type': 'application/json'}
            )
            return json.loads(response.text)
        except Exception as e:
            logger.error(f"Keyword extraction failed: {e}")
            return []

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

    def analyze_drive_for_organization(self, folders: list, loose_files: list) -> dict:
        """
        分析 Drive 根目錄散檔並產生整理計畫。

        Args:
            folders: 既有資料夾清單 [{name, id}]
            loose_files: 根目錄散檔 [{name, mimeType, size, modifiedTime}]

        Returns:
            dict: {
                "actions": [
                    {"type": "create_folder", "folder_name": "...", "reason": "..."},
                    {"type": "move", "file_name": "...", "file_id": "...",
                     "target_folder": "...", "target_is_new": true/false, "reason": "..."}
                ],
                "summary": "整體說明"
            }
        """
        # 準備資料夾和檔案清單文字
        folder_list = "\n".join([f"  📁 {f['name']}" for f in folders]) if folders else "  （無）"
        file_list = "\n".join([
            f"  📄 [ID:{f['id']}] {f['name']} ({f.get('mimeType', 'unknown')}, "
            f"修改: {f.get('modifiedTime', 'N/A')[:10]})"
            for f in loose_files
        ]) if loose_files else "  （無）"

        system_instruction = f"""{ALICE_PERSONA}

你現在是專業的檔案管理助手。仁哥的 Google 雲端硬碟根目錄有一些散檔需要整理。

【已有的資料夾】
{folder_list}

【根目錄散檔】
{file_list}

請分析這些散檔，產生一個合理的整理計畫。

📏 規則：
1. 只能「建立資料夾」和「移動檔案」，**禁止刪除**
2. 優先使用已有的資料夾，只在確實需要時才建立新資料夾
3. 資料夾名稱要簡潔有意義（如：「合約文件」「照片素材」「財務報表」）
4. 相似類型的檔案歸為同一類
5. 如果某檔案不確定分類，就不動它
6. 如果散檔很少或已經很整齊，可以回傳空的 actions

📤 回傳 JSON 格式：
{{
  "actions": [
    {{"type": "create_folder", "folder_name": "新資料夾名", "reason": "原因"}},
    {{"type": "move", "file_name": "檔案名", "file_id": "檔案的ID（[ID:xxx]中的xxx）",
      "target_folder": "目標資料夾名", "target_is_new": true, "reason": "原因"}}
  ],
  "summary": "整體說明（1-2句話）"
}}

⚠️ 重要：file_id 必須使用上方散檔清單中 [ID:xxx] 裡的值，這是 Google Drive 的檔案識別碼。
              絕對不要用檔案名稱當 file_id！
"""
        try:
            response = self.client.models.generate_content(
                model=self.model_id,
                contents="請分析上述 Drive 結構並產生整理計畫。",
                config={
                    'system_instruction': system_instruction,
                    'response_mime_type': 'application/json'
                }
            )
            result = json.loads(response.text)
            logger.info(f"📋 Drive 整理分析完成: {len(result.get('actions', []))} 項動作")
            return result

        except json.JSONDecodeError as e:
            logger.error(f"❌ Drive 分析 JSON 解析失敗: {e}")
            return {"actions": [], "summary": "分析結果格式異常，請稍後再試。"}
        except Exception as e:
            logger.error(f"❌ Drive 分析失敗: {e}")
            return {"actions": [], "summary": f"分析時發生錯誤：{str(e)}"}

