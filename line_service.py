import os
import requests

def send_line_message(message):
    """透過 Line Messaging API 傳送訊息。"""
    line_token = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
    user_id = os.getenv("LINE_USER_ID")
    
    if not line_token or not user_id:
        print("未設定 LINE_CHANNEL_ACCESS_TOKEN 或 LINE_USER_ID，訊息將輸出至控制台。")
        print("-" * 20)
        print(message)
        print("-" * 20)
        return
    
    url = "https://api.line.me/v2/bot/message/push"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {line_token}"
    }
    payload = {
        "to": user_id,
        "messages": [
            {
                "type": "text",
                "text": message
            }
        ]
    }
    
    response = requests.post(url, headers=headers, json=payload)
    if response.status_code != 200:
        print(f"Line 訊息傳送失敗: {response.text}")
    else:
        print("Line 訊息傳送成功！")
