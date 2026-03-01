import requests
import json
import os
from dotenv import load_dotenv

load_dotenv(override=True)

LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")

def delete_all_rich_menus():
    """
    刪除所有舊的 Rich Menu，確保環境乾淨。
    """
    headers = {'Authorization': f'Bearer {LINE_CHANNEL_ACCESS_TOKEN}'}
    # 列出所有選單
    response = requests.get('https://api.line.me/v2/bot/richmenu/list', headers=headers)
    if response.status_code == 200:
        menus = response.json().get('richmenus', [])
        for menu in menus:
            menu_id = menu['richMenuId']
            requests.delete(f'https://api.line.me/v2/bot/richmenu/{menu_id}', headers=headers)
            print(f"已刪除舊選單: {menu_id}")

def create_and_link_rich_menu(user_id, image_path="rich_menu_v2_FINAL_CLOSEUP.jpg"):
    """
    建立 3x3 網格結構的 Rich Menu (前兩欄為功能，第三欄為背景圖像)。
    """
    headers = {
        'Authorization': f'Bearer {LINE_CHANNEL_ACCESS_TOKEN}',
        'Content-Type': 'application/json'
    }

    # Grid: 3 columns, 3 rows.
    # W=2500, H=1686.
    # cw = 833, ch = 562
    rich_menu_data = {
        "size": {"width": 2500, "height": 1686},
        "selected": True,
        "name": "AI Secretary Pro v2.2",
        "chatBarText": "📂 秘書選單",
        "areas": [
            # Row 0
            {
                "bounds": {"x": 0, "y": 0, "width": 833, "height": 562},
                "action": {"type": "message", "text": "📂 今日簡報"}
            },
            {
                "bounds": {"x": 833, "y": 0, "width": 834, "height": 562},
                "action": {"type": "message", "text": "📸 視覺助理"}
            },
            # Row 1
            {
                "bounds": {"x": 0, "y": 562, "width": 833, "height": 562},
                "action": {"type": "message", "text": "🗓️ 行程管理"}
            },
            {
                "bounds": {"x": 833, "y": 562, "width": 834, "height": 562},
                "action": {"type": "message", "text": "✉️ 智慧回信"}
            },
            # Row 2
            {
                "bounds": {"x": 0, "y": 1124, "width": 833, "height": 562},
                "action": {"type": "message", "text": "✅ 待辦清單"}
            },
            {
                "bounds": {"x": 833, "y": 1124, "width": 834, "height": 562},
                "action": {"type": "message", "text": "🧠 記憶核心"}
            },
            # Decorative / Secretary Area (Right Column)
            {
                "bounds": {"x": 1667, "y": 0, "width": 833, "height": 1686},
                "action": {"type": "message", "text": "Alice，妳好！"}
            }
        ]
    }

    # 先清理舊的
    delete_all_rich_menus()

    # 1. 建立 Rich Menu
    response = requests.post(
        'https://api.line.me/v2/bot/richmenu',
        headers=headers,
        data=json.dumps(rich_menu_data)
    )
    rich_menu_data_resp = response.json()
    rich_menu_id = rich_menu_data_resp.get('richMenuId')
    
    if not rich_menu_id:
        print(f"建立 Rich Menu 失敗: {response.text}")
        return

    print(f"成功建立 Rich Menu ID: {rich_menu_id}")

    # 2. 上傳圖片
    with open(image_path, 'rb') as f:
        img_headers = {
            'Authorization': f'Bearer {LINE_CHANNEL_ACCESS_TOKEN}',
            'Content-Type': 'image/jpeg'
        }
        upload_response = requests.post(
            f'https://api-data.line.me/v2/bot/richmenu/{rich_menu_id}/content',
            headers=img_headers,
            data=f
        )
    
    if upload_response.status_code == 200:
        print("圖片上傳成功！")
    else:
        print(f"圖片上傳失敗: {upload_response.text}")
        return

    # 3. 綁定給當前使用者
    link_response = requests.post(
        f'https://api.line.me/v2/bot/user/{user_id}/richmenu/{rich_menu_id}',
        headers={'Authorization': f'Bearer {LINE_CHANNEL_ACCESS_TOKEN}'}
    )
    
    if link_response.status_code == 200:
        print(f"✅ 成功將新版選單綁定到您的 LINE 帳號！")
        print(f"📌 請注意：若畫面未更新，請『完全關閉 LINE App 並重開』或『刪除聊天室記錄重進』。")
    else:
        print(f"綁定失敗: {link_response.text}")

if __name__ == "__main__":
    my_user_id = os.getenv("LINE_USER_ID")
    if my_user_id:
        create_and_link_rich_menu(my_user_id)
    else:
        print("請在 .env 中設定 LINE_USER_ID")
