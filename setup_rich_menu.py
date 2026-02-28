import requests
import json
import os
from dotenv import load_dotenv

load_dotenv(override=True)

LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")

def create_and_link_rich_menu(user_id, image_path="rich_menu.png"):
    """
    建立 Rich Menu、上傳背景圖片並綁定給指定使用者。
    """
    
    headers = {
        'Authorization': f'Bearer {LINE_CHANNEL_ACCESS_TOKEN}',
        'Content-Type': 'application/json'
    }

    # 1. 定義 Rich Menu 結構 (3 格: 行程, 主動處理, 信件)
    # 注意：這裡的 size 與背景圖片解析度需匹配 (2500x843 或 2500x1686)
    rich_menu_data = {
        "size": {"width": 2500, "height": 1686},
        "selected": True,
        "name": "AI Secretary Premium Menu",
        "chatBarText": "📂 秘書選單",
        "areas": [
            {
                "bounds": {"x": 0, "y": 0, "width": 833, "height": 1686},
                "action": {"type": "message", "text": "今天有什麼行程？"}
            },
            {
                "bounds": {"x": 833, "y": 0, "width": 834, "height": 1686},
                "action": {"type": "message", "text": "幫我整理今日代辦並起草回信"}
            },
            {
                "bounds": {"x": 1667, "y": 0, "width": 833, "height": 1686},
                "action": {"type": "message", "text": "有新信件嗎？"}
            }
        ]
    }

    # 2. 建立 Rich Menu 並取得 ID
    response = requests.post(
        'https://api.line.me/v2/bot/richmenu',
        headers=headers,
        data=json.dumps(rich_menu_data)
    )
    rich_menu_id = response.json().get('richMenuId')
    
    if not rich_menu_id:
        print(f"建立 Rich Menu 失敗: {response.text}")
        return

    print(f"成功建立 Rich Menu ID: {rich_menu_id}")

    # 3. 上傳圖片
    with open(image_path, 'rb') as f:
        img_headers = {
            'Authorization': f'Bearer {LINE_CHANNEL_ACCESS_TOKEN}',
            'Content-Type': 'image/png'
        }
        upload_response = requests.post(
            f'https://api-data.line.me/v2/bot/richmenu/{rich_menu_id}/content',
            headers=img_headers,
            data=f
        )
    
    if upload_response.status_code == 200:
        print("圖片上傳成功！")
    else:
        print(f"圖片上傳失敗，狀態碼: {upload_response.status_code}")
        print(f"回應內容: {upload_response.text}")
        return

    # 4. 綁定 ID 到使用者
    link_response = requests.post(
        f'https://api.line.me/v2/bot/user/{user_id}/richmenu/{rich_menu_id}',
        headers={
            'Authorization': f'Bearer {LINE_CHANNEL_ACCESS_TOKEN}'
        }
    )
    
    if link_response.status_code == 200:
        print(f"成功將精美選單綁定到您的 LINE 帳號！\n(請重新開啟 LINE 聊天室查看)")
    else:
        print(f"綁定選單失敗: {link_response.text}")

    return rich_menu_id

if __name__ == "__main__":
    my_user_id = os.getenv("LINE_USER_ID")
    if my_user_id:
        create_and_link_rich_menu(my_user_id)
    else:
        print("請在 .env 中設定 LINE_USER_ID")
