from google import genai
import os

def generate_report(events, emails, prompt_path):
    """使用最新 Google GenAI SDK 生成行政秘書匯報。"""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("請設定 GEMINI_API_KEY 環境變數。")
    
    # 清理 API KEY (處理可能重複貼上的問題)
    api_key = api_key.strip().replace('"', '').replace("'", "")
    if len(api_key) == 78:
        api_key = api_key[:39]
    
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
