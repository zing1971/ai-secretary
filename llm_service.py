import google.generativeai as genai
import os

def generate_report(events, emails, prompt_path):
    """使用 Gemini 生成行政秘書匯報。"""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("請設定 GEMINI_API_KEY 環境變數。")
    
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    with open(prompt_path, "r", encoding="utf-8") as f:
        system_prompt = f.read()
    
    # 組合 User Input
    user_input = "以下是今日資訊：\n\n- 行事曆事件：\n"
    user_input += "\n".join(events) if events else "今日無行程。"
    user_input += "\n\n- 信件清單：\n"
    user_input += "\n".join(emails) if emails else "過去 24 小時無新信件。"
    
    chat = model.start_chat(history=[])
    response = chat.send_message(f"{system_prompt}\n\n{user_input}")
    
    return response.text
