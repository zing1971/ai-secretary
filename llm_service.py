from google import genai
import os
import json
from google_auth import clean_api_key

def generate_report(events, emails, prompt_path):
    """使用最新 Google GenAI SDK 生成行政秘書匯報。"""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("請設定 GEMINI_API_KEY 環境變數。")
    
    api_key = clean_api_key(api_key)
    
    # 初始化最新 Client
    client = genai.Client(api_key=api_key)
    
    # 讀取系統提示詞
    with open(prompt_path, "r", encoding="utf-8") as f:
        system_prompt = f.read()
    
    # 準備輸入資料
    user_input = "以下是今日資訊：\n\n- 行事曆事件：\n"
    user_input += "\n".join(events) if events else "今日無行程。"
    user_input += "\n\n- 信件清單：\n"
    user_input += "\n".join(emails) if emails else "過去 24 小時無新信件。"
    
    # 呼叫 Gemini (使用最新 SDK 語彙)
    response = client.models.generate_content(
        model='gemini-2.0-flash',
        contents=user_input,
        config={
            'system_instruction': system_prompt
        }
    )
    
    return response.text

def analyze_for_actions(events, emails):
    """分析行程與信件，萃取出待辦事項與回覆草稿建議。"""
    api_key = os.getenv("GEMINI_API_KEY")
    client = genai.Client(api_key=api_key)
    
    system_instruction = """你是一位高階主管的專業 AI 行政秘書。
你的任務是從老闆提供的今日行程與信件摘要中，主動找出「需要老闆處理的待辦事項」以及「需要回覆的信件」。
請將結果輸出為 JSON 格式，如下：

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
    
    response = client.models.generate_content(
        model='gemini-2.0-flash',
        contents=f"請分析以下數據並提供主動處理建議：\n\n{user_data}",
        config={
            'system_instruction': system_instruction,
            'response_mime_type': 'application/json'
        }
    )
    
    return json.loads(response.text)
