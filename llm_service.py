import json
import os
from datetime import datetime
import pytz
from google import genai
from config import Config, logger
from google_auth import clean_api_key
from shared.llm_prompts import ALICE_PERSONA, BIRDIE_PERSONA


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
        """根據使用者訊息與長期記憶生成回覆（含防幻覺護欄）"""
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
- 資料來源標註：🧠 Alice / 記憶核心
- 如果是一般問候或閒聊 → 不需要標註資料來源。
- 不要複述仁哥的問題，直接回答。

⚠️【防幻覺護欄 — 嚴格遵守】
- 你只是行政秘書，不是專業顧問、搜尋引擎或百科全書。
- 如果仁哥問的問題涉及「資安、IT、法規、技術架構、政策、合規」等專業知識
  → 絕對不能用你自身的知識回答！
  → 應引導仁哥使用專業查詢，回覆範例：
  「仁哥，這個問題建議讓 Alice 幫您查一下知識庫，會更準確喔！請說『查知識庫 OOO』😊」
- 如果仁哥問的是即時資訊（天氣、股價、新聞、賽事）
  → 同樣不能猜測，應引導：
  「仁哥，這個需要查最新資訊，讓 Alice 幫您上網搜尋好嗎？請說『上網查 OOO』🌐」
- 只有以下情況才能直接回答：
  ① 問候閒聊（早安、謝謝、你好）
  ② 記憶中確實有記錄的事情
  ③ Alice 自身能力相關的問題（你會什麼、怎麼用你）
  ④ 日常生活常識（不涉及專業或即時性的問題）
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

    def format_calendar_response(self, events: list, time_label: str, user_msg: str, memories: str = "", search_keyword: str = "") -> str:
        """根據行事曆行程與秘書觀點，用 Alice 口吻生成格式化回覆"""
        current_time = _get_current_time_str()
        
        events_str = "\n".join(events) if events else "無已排定行程"
        keyword_context = f"【指定搜尋關鍵字】{search_keyword}\n（注意：這是針對特定關鍵字的查詢結果，回答語氣請直接針對此事件）" if search_keyword else ""
        
        system_instruction = f"""{ALICE_PERSONA}

【當前時間】{current_time}

你的任務是根據仁哥查詢的行事曆結果（{time_label}），以專業行政秘書的角度回報，並提供貼心建議。

【仁哥的長期記憶與偏好】
---
{memories}
---

【查詢時段】{time_label}
{keyword_context}
【行程清單】
{events_str}

【回覆結構要求】
1. 開頭問候：簡短報告查詢結果（例如：「仁哥，為您整理{time_label}的行程：」）。若是條件搜尋，請用：「關於您詢問的主題，我找到了以下安排：」
2. 行程清單：如果沒有行程，簡單帶過；如果有，清晰列出。如果是針對特定會議（例如「下次業務會議」）且只有一兩筆，可以使用敘述句（例如：「下次業務會議安排在...」）代替條列。
3. 💡 秘書貼心建議（這是重點）：
   - 審視行程密集度：若行程過度密集 (Back-to-back)，提醒保留喘息時間、喝杯水或適當安排用餐。
   - 行程前準備：若有重要會議，提醒是否需要準備資料、前置作業或提早出發。
   - 連結記憶：若會議參與者、標題或地點與上方「長期記憶」有關，巧妙帶入貼心提醒。
   - 關懷鼓勵：若行程空檔多，可提醒處理待辦；若完全沒有行程，給予溫暖的問候（如：終於可以好好放鬆休息了）。
4. 格式：使用清晰的列表，將「行程清單」與「💡 秘書貼心建議」分開段落顯示，適度使用 emoji。
5. **必須在結尾加上資料來源標註**：
   ══════════════
   📍 資料來源：📅 Google Calendar / 行事曆

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

    def format_tasks_response(self, tasks: list, user_msg: str, memories: str = "") -> str:
        """將待辦清單格式化為 Alice 的口吻"""
        current_time = _get_current_time_str()
        tasks_str = "\n".join(tasks) if tasks else "目前沒有未完成的待辦任務"
        
        system_instruction = f"""{ALICE_PERSONA}
【當前時間】{current_time}
【仁哥的記憶】
{memories}

你的任務是幫仁哥檢查 Google Tasks 上的待辦項目，並給予細心的提醒。
如果清單很多，可以挑選出優先順序高的標記出來。

【任務清單】
{tasks_str}

回覆格式：
1. 秘書報告
2. 清單（使用 ✅ 或 ⏳ 標記狀態）
3. 貼心叮嚀
4. **必須在結尾加上資料來源標註**：
   ══════════════
   📍 資料來源：✅ Google Tasks / 待辦清單
"""
        try:
            response = self.client.models.generate_content(
                model=self.model_id,
                contents=f"請幫我整理待辦清單。仁哥問：「{user_msg}」",
                config={'system_instruction': system_instruction}
            )
            return response.text
        except Exception as e:
            logger.error(f"Tasks formatting failed: {e}")
            return f"✅ 仁哥，您的待辦事項如下：\n{tasks_str}\n\n加油喔！Alice 會在旁邊支援您的 💪"

    def format_drive_search_results(self, files: list, user_msg: str) -> str:
        """根據 Google Drive 搜尋結果，用 Alice 口吻生成格式化回覆"""
        if not files:
            return "仁哥，抱歉，我剛剛在雲端硬碟裡找過了，沒有發現符合的檔案喔 😥"

        files_info = "\n".join([f"- [{f.get('name')}]({f.get('webViewLink')})" for f in files])
        
        system_instruction = f"""{ALICE_PERSONA}

你的任務是根據 Google Drive 的搜尋結果，生動地回報給仁哥。

【搜尋結果】
{files_info}

【回覆規則】
1. 語氣溫柔專業，像是親手幫老闆找到檔案一樣。
2. 開頭可以說「仁哥，我幫您找到了這幾份相關的檔案：」或類似的自然開場。
3. 把檔案清單完整貼出來，保留 Markdown 連結格式。
4. 結尾可以加一句貼心問候（例如：希望能幫上您的忙、如果有需要找別的再跟我說）。
5. 直接點出重點，不要解釋搜尋過程。
6. 注意：直接輸出一般文字對話，千萬不要使用 Markdown 的程式碼區塊（```）包裝整個回覆。
7. **必須在結尾加上資料來源標註**：
   ══════════════
   📍 資料來源：📂 Google Drive / 雲端硬碟
"""
        try:
            response = self.client.models.generate_content(
                model=self.model_id,
                contents=f"請回報搜尋結果。仁哥問：「{user_msg}」",
                config={'system_instruction': system_instruction}
            )
            return response.text.strip('```markdown\n').strip('```\n').strip('```')
        except Exception as e:
            logger.error(f"Drive search formatting failed: {e}")
            return f"仁哥，我找到了這些檔案，請過目：\n{files_info}"

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
        
        system_instruction = f"""{BIRDIE_PERSONA}

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
「仁哥，今天目前沒有急需處理的事務，可以專心投入工作！Birdie 會持續幫您留意的 💪」
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

    def format_email_summary(self, emails: list, user_msg: str, memories: str = "", search_keyword: str = "") -> str:
        """過濾並摘要重點信件（含 URL 引用）"""
        if not emails:
            return "仁哥，為您搜尋後目前沒有符合的相關信件。"
            
        # 組合信件資料（含 URL）
        emails_str_list = []
        for i, email in enumerate(emails):
            snippet = email.get('body', email.get('snippet', '無內容'))[:300]
            url = email.get('url', '')
            url_info = f" | URL: {url}" if url else ""
            emails_str_list.append(f"[信件 {i+1}] 寄件人: {email['sender']} | 主旨: {email['subject']}{url_info}\n內容開頭: {snippet}")
        
        emails_str = "\n".join(emails_str_list)
        keyword_context = f"【搜尋目標】{search_keyword}\n" if search_keyword else ""
        
        system_instruction = f"""{ALICE_PERSONA}

你的任務是根據仁哥查詢的要求，過濾並整理最近的信件清單。
【仁哥的記憶與偏好】
{memories}

{keyword_context}
【最新信件清單（最多15封片段）】
{emails_str}

【回覆準則】
1. 過濾掉明顯的廣告信、通知信或是無關緊要的系統信（除非這些信件符合仁哥指定的搜尋關鍵字）。
2. 只列出「重要」、「需要處理/回覆」或「與仁哥詢問意圖高度相關」的信件（最好控制在 3~5 封內）。
3. 針對挑出的每一封信件，列出：寄件人、重點摘要。
4. 如果信件資料中有 URL，在每封重要信件摘要後附上「🔗 查看原信：URL」（最多附 3 封）。
5. 如果沒有找到任何重要信件，請回報「目前信箱很乾淨喔」或「沒有找到相關信件」。
6. 最後給予一句秘書的貼心建議。
7. **必須在結尾加上資料來源標註**：
   ══════════════
   📍 資料來源：📧 Gmail / 電子郵件


請直接給出傳給仁哥的 LINE 訊息文字，不需要自我介紹或多餘的解說。
"""
        try:
            response = self.client.models.generate_content(
                model=self.model_id,
                contents=f"請幫我分析這批信件，仁哥說：「{user_msg}」",
                config={'system_instruction': system_instruction}
            )
            return response.text
        except Exception as e:
            logger.error(f"Gemini email filtering failed: {e}")
            return f"📧 仁哥，系統目前無法幫您進行智慧過濾，為您列出前 3 封信的標題：\n" + "\n".join([e['summary_text'] for e in emails[:3]])

    def generate_email_draft_reply(self, email_data: dict, user_msg: str, memories: str = "") -> str:
        """根據信件內容與使用者指示，自動生成回信草稿"""
        system_instruction = f"""{BIRDIE_PERSONA}
你現在的具體任務是擬寫一封回信。
你的任務是根據一封收到的信件，以及仁哥簡單的指令，撰寫一篇正式、得體的回信內容。

【仁哥的風格或相關記憶】
{memories}

【原始信件資訊】
寄件人：{email_data.get('sender', '未知')}
主旨：{email_data.get('subject', '無主旨')}
內容：
{email_data.get('body', '無內容')}

【撰寫準則】
1. 語氣必須以「仁哥（或他的職稱，如果長期記憶中有記載）」的名義發出，或者以「仁哥的秘書 Alice 代為回覆」的名義發出（根據上下文判斷何者合適，預設以仁哥名義）。
2. 信件內容要符合職場正式禮儀，首尾要有合適的問候與敬語。
3. 緊扣仁哥給予的指示。
4. **絕對不要**輸出任何 markdown 格式符號（如 ``` 等），請直接回傳信件的純文字內容。
"""
        try:
            response = self.client.models.generate_content(
                model=self.model_id,
                contents=f"請幫我擬一封此信的回覆。仁哥的交代是：「{user_msg}」",
                config={'system_instruction': system_instruction}
            )
            return response.text.strip()
        except Exception as e:
            logger.error(f"Gemini draft generation failed: {e}")
            return "無法根據內容產生合適的回覆，請見諒。"

    def analyze_image_for_actions(self, image_bytes: bytes) -> dict:
        """分析使用者傳來的圖片內容，進行多模態處理，並回傳結構化資料"""
        from google.genai import types
        import json
        
        system_instruction = f"""{BIRDIE_PERSONA}

你在扮演 Birdie 管家。現在仁哥傳了一張圖片給你。
請發揮專業行政秘書的視覺能力，根據圖片內容判斷並回傳 JSON：

【分析準則】
1. 早安圖 / 一般風景照：不要建立任務或聯絡人，只需要給予充滿活力的溫暖問候。
2. 名片：萃取出姓名、公司、職稱、Email、電話，放進 `contacts` 陣列。
3. 白板 / 筆記會議紀錄：擷取出會議的重點。並分析出明顯是「待辦事項」的東西放入 `tasks` 陣列（due 給予一個合理的推斷時間，如果沒有提到日期則留空 ""）。
4. 發票 / 收據檔：擷取出總金額、日期，並可以選擇是否建一個待辦任務「備忘: 確認帳務與請款」。

【JSON 輸出格式】（嚴格遵守，禁止使用 Markdown 包裝或回傳額外文字）
{{
    "tasks": [
        {{"title": "任務標題", "notes": "細節補充", "due": ""}}
    ],
    "contacts": [
        {{"name": "姓名", "company": "公司", "job_title": "職稱", "email": "電子郵件", "phone": "電話"}}
    ],
    "briefing": "用繁體中文，溫暖且專業的語氣向仁哥報告你看到了什麼、整理了什麼。注意：不要詢問是否需要進一步動作（例如草擬信件、建立行事曆等），因為圖片處理是單次動作，Alice 無法接收後續回覆。只需要確認已完成的事項即可。這是傳送在 LINE 裡的文字，記得排版清楚、善用 emoji。"
}}
"""
        try:
            response = self.client.models.generate_content(
                model=self.model_id,
                contents=[
                    "仁哥剛傳來了這張圖片，請幫忙看看並處理此任務。",
                    types.Part.from_bytes(data=image_bytes, mime_type='image/jpeg')
                ],
                config={
                    'system_instruction': system_instruction,
                    'response_mime_type': 'application/json'
                }
            )
            return json.loads(response.text.strip())
        except json.JSONDecodeError as e:
            logger.error(f"Gemini image JSON parse error: {e}")
            return "仁哥抱歉，Birdie 看懂了圖片，但是大腦整理資訊時出了點格式問題 🙇‍♀️"
        except Exception as e:
            logger.error(f"Gemini image analysis failed: {e}")
            return "仁哥抱歉，Birdie 的「眼睛」出了一點小狀況，現在無法看清楚這張圖片 🙇‍♀️"

    def format_domain_advisor_reply(self, query: str, domain: str, notebooklm_answer: str, source_url: str = "") -> str:
        """根據領域 (資安/IT/趨勢) 與知識庫答案，生成 Alice 的專業顧問報告"""
        domain_labels = {
            "infosec": "資通安全",
            "it": "資訊科技",
            "trends": "國際趨勢"
        }
        domain_label = domain_labels.get(domain, "專業領域")
        
        # 組合來源標註（含 URL）
        source_section = "══════════════\n📍 資料來源：📚 NotebookLM / 專案知識庫"
        if source_url:
            source_section += f"\n🔗 開啟知識庫：{source_url}"
        
        system_instruction = f"""{ALICE_PERSONA}

你現在是高階主管專屬的 AI 秘書 Alice。主管剛才向你詢問了關於【{domain_label}】的議題。
你已經在內部的「戰略知識庫 (NotebookLM)」中檢索了相關文件，取得了以下原始資料：
{notebooklm_answer}

<任務指南>
請依照以下原則，將原始資料轉化為給主管的正式報告：
1. 【語點要求】：保持一貫的溫柔、專業、細心（例如：「報告仁哥...」、「為您整理了以下重點...」）。
2. 【依據領域深化解析】：
   - 若為「資通安全」：必須強調潛在風險、合規性要求（如法規遵循）、以及建議的防禦或應對措施。
   - 若為「資訊科技」：著重於技術架構的合理性、系統導入效率、以及對現有業務的影響評估。
   - 若為「國際趨勢」：需點出對台灣或現有市場的啟示、競爭者可能動向，並給出高階的戰略建議。
3. 【排版結構】：
   - 先用一句話總結核心發現。
   - 列點說明重要細節（最多 3-4 點，條理分明）。
   - 【加入追問建議】：根據原始資料判斷還有哪方面可以深挖，在結尾加上如「您想進一步了解 OOO 的細節嗎？」。
4. 【資料忠實度】：絕不能捏造知識庫中未提及的數據。
5. **必須在結尾加上以下資料來源標註（原封不動）**：
   {source_section}

請直接輸出 LINE 訊息內容。
"""
        try:
            response = self.client.models.generate_content(
                model=self.model_id,
                contents=f"請幫我將知識庫答案轉化為對仁哥的專業報告。問題是：「{query}」",
                config={'system_instruction': system_instruction}
            )
            return response.text
        except Exception as e:
            logger.error(f"Domain advisor formatting failed: {e}")
            return f"報告仁哥，關於您詢問的「{query}」，我從知識庫查到的重點如下：\n\n{notebooklm_answer}\n\n希望這些資訊對您有幫助 🙇‍♀️"

    def format_web_search_reply(self, query: str, search_results: str) -> str:
        """格式化網際網路搜尋結果"""
        system_instruction = f"""{ALICE_PERSONA}

你的任務是根據網際網路搜尋到的即時資訊，為仁哥提供簡明扼要的回答。

【搜尋結果摘要】
{search_results}

【回覆準則】
1. 語氣溫柔專業。
2. 提取最關鍵的資訊回答（例如：今天的天氣、最新的新聞動向、或是特定的知識）。
3. 如果結果不完整，誠實告知仁哥。
4. **必須在結尾加上資料來源標註**：
   ══════════════
   📍 資料來源：🌐 Internet / 網際網路

請直接輸出 LINE 訊息內容。
"""
        try:
            response = self.client.models.generate_content(
                model=self.model_id,
                contents=f"請幫我整理搜尋結果。仁哥問：「{query}」",
                config={'system_instruction': system_instruction}
            )
            return response.text
        except Exception as e:
            logger.error(f"Web search formatting failed: {e}")
            return f"報告仁哥，關於「{query}」，我從網路上查到了一些內容，但整理時出了點狀況... 🙇‍♀️\n\n{search_results[:500]}"

    def perform_web_search(self, query: str) -> str:
        """使用 Google Search Grounding 執行網路搜尋並直接格式化回覆"""
        system_instruction = f"""{ALICE_PERSONA}

【任務】
你現在化身為網路情資專家。仁哥詢問了一鍵即時資訊。
請利用 Google 搜尋工具獲取最準確的資料，並以 Alice 的口吻回報。

【回覆準則】
1. 語氣溫柔專業。
2. 提取最關鍵的資訊回答。
3. **必須在結尾加上資料來源標註**：
   ══════════════
   📍 資料來源：🌐 Internet / 網際網路

請直接輸出 LINE 訊息內容。
"""
        try:
            # 啟用 Google Search Tool
            tools = [
                {'google_search': {}}
            ]
            
            response = self.client.models.generate_content(
                model=self.model_id,
                contents=f"搜尋並回答：{query}",
                config={
                    'system_instruction': system_instruction,
                    'tools': tools
                }
            )
            return response.text
        except Exception as e:
            logger.error(f"Google Search Grounding failed: {e}")
            return f"報告仁哥，原本想幫您上網查「{query}」，但 Alice 的網路搜尋模組暫時斷線了 🙇‍♀️"

