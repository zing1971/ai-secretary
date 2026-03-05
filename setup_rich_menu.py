"""
LINE Rich Menu 設定腳本 — 雙角色版 (Alice + Birdie)

版面配置：4 欄 × 3 列 (共 12 個按鈕)
左半區：Alice 查詢功能（行程、信件、網路、知識庫、待辦、檔案）
右半區：Birdie 執行功能（簡報、擬稿、整理雲端、視覺、記憶、閒聊）
"""
import requests
import json
import os
from dotenv import load_dotenv

load_dotenv(override=True)

LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")


def delete_all_rich_menus():
    """刪除所有舊的 Rich Menu，確保環境乾淨。"""
    headers = {'Authorization': f'Bearer {LINE_CHANNEL_ACCESS_TOKEN}'}
    response = requests.get('https://api.line.me/v2/bot/richmenu/list', headers=headers)
    if response.status_code == 200:
        menus = response.json().get('richmenus', [])
        for menu in menus:
            menu_id = menu['richMenuId']
            requests.delete(f'https://api.line.me/v2/bot/richmenu/{menu_id}', headers=headers)
            print(f"已刪除舊選單: {menu_id}")


def create_and_link_rich_menu(user_id, image_path="rich_menu_v3_dual_role.jpg"):
    """
    建立 4×3 雙角色 Rich Menu。
    左半：Alice（情報秘書）查詢功能
    右半：Birdie（執行管家）執行功能
    """
    headers = {
        'Authorization': f'Bearer {LINE_CHANNEL_ACCESS_TOKEN}',
        'Content-Type': 'application/json'
    }

    # 尺寸：2500 × 1686
    # 4 欄 × 3 列，每格 625 × 562
    W, H = 2500, 1686
    CW, CH = 625, 562

    rich_menu_data = {
        "size": {"width": W, "height": H},
        "selected": True,
        "name": "AI Secretary v3.0 — Alice + Birdie",
        "chatBarText": "🎭 秘書選單",
        "areas": [
            # ===== Row 0 =====
            # [Alice] 行程查詢
            {
                "bounds": {"x": 0, "y": 0, "width": CW, "height": CH},
                "action": {"type": "message", "text": "Alice，幫我看看最近的行程安排"}
            },
            # [Alice] 信件查詢
            {
                "bounds": {"x": CW, "y": 0, "width": CW, "height": CH},
                "action": {"type": "message", "text": "Alice，檢查最新重要郵件"}
            },
            # [Birdie] 今日簡報
            {
                "bounds": {"x": CW * 2, "y": 0, "width": CW, "height": CH},
                "action": {"type": "message", "text": "Birdie，今天的工作簡報"}
            },
            # [Birdie] 智慧擬稿
            {
                "bounds": {"x": CW * 3, "y": 0, "width": CW, "height": CH},
                "action": {"type": "message", "text": "Birdie，幫我擬回信草稿"}
            },

            # ===== Row 1 =====
            # [Alice] 網路搜尋
            {
                "bounds": {"x": 0, "y": CH, "width": CW, "height": CH},
                "action": {"type": "message", "text": "Alice，上網查最新資訊"}
            },
            # [Alice] 知識庫查詢
            {
                "bounds": {"x": CW, "y": CH, "width": CW, "height": CH},
                "action": {"type": "message", "text": "Alice，查一下知識庫"}
            },
            # [Birdie] 整理雲端
            {
                "bounds": {"x": CW * 2, "y": CH, "width": CW, "height": CH},
                "action": {"type": "message", "text": "Birdie，整理雲端硬碟"}
            },
            # [Birdie] 視覺處理
            {
                "bounds": {"x": CW * 3, "y": CH, "width": CW, "height": CH},
                "action": {"type": "message", "text": "📸 Birdie，幫忙視覺分析處理照片"}
            },

            # ===== Row 2 =====
            # [Alice] 待辦查詢
            {
                "bounds": {"x": 0, "y": CH * 2, "width": CW, "height": CH},
                "action": {"type": "message", "text": "Alice，整理待辦事項"}
            },
            # [Alice] 搜尋檔案
            {
                "bounds": {"x": CW, "y": CH * 2, "width": CW, "height": CH},
                "action": {"type": "message", "text": "Alice，搜尋雲端檔案"}
            },
            # [Birdie] 記憶管理
            {
                "bounds": {"x": CW * 2, "y": CH * 2, "width": CW, "height": CH},
                "action": {"type": "message", "text": "Birdie，關於我的偏好記住了什麼？"}
            },
            # [共用] 與我閒聊
            {
                "bounds": {"x": CW * 3, "y": CH * 2, "width": CW, "height": CH},
                "action": {"type": "message", "text": "嗨，你們好！"}
            },
        ]
    }

    # 清理舊的
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
        print(f"❌ 建立 Rich Menu 失敗: {response.text}")
        return

    print(f"✅ 成功建立 Rich Menu ID: {rich_menu_id}")

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
        print("✅ 圖片上傳成功！")
    else:
        print(f"❌ 圖片上傳失敗: {upload_response.text}")
        return

    # 3. 綁定給使用者
    link_response = requests.post(
        f'https://api.line.me/v2/bot/user/{user_id}/richmenu/{rich_menu_id}',
        headers={'Authorization': f'Bearer {LINE_CHANNEL_ACCESS_TOKEN}'}
    )

    if link_response.status_code == 200:
        print(f"✅ 雙角色選單已綁定成功！")
        print(f"📌 若畫面未更新，請完全關閉 LINE App 並重開。")
    else:
        print(f"❌ 綁定失敗: {link_response.text}")


if __name__ == "__main__":
    my_user_id = os.getenv("LINE_USER_ID")
    if my_user_id:
        create_and_link_rich_menu(my_user_id)
    else:
        print("請在 .env 中設定 LINE_USER_ID")
