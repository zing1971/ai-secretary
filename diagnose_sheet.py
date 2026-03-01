from google_auth import get_google_services
from config import Config
import os
from dotenv import load_dotenv

def diagnostic_sheet():
    load_dotenv(override=True)
    print(f"🔍 診斷試算表 ID: {Config.GOOGLE_SHEET_ID}")
    
    try:
        gmail, calendar, tasks, sheets, drive = get_google_services()
        
        # 1. 取得試算表資訊，確認名稱
        spreadsheet = sheets.spreadsheets().get(spreadsheetId=Config.GOOGLE_SHEET_ID).execute()
        sheet_name = spreadsheet['sheets'][0]['properties']['title']
        print(f"📌 偵測到第一張工作表名稱為: '{sheet_name}'")
        
        # 2. 嘗試寫入 (使用偵測到的名稱)
        test_range = f"'{sheet_name}'!A:B"
        body = {'values': [['測試時間', '診斷測試內容']]}
        
        print(f"🚀 嘗試寫入範圍: {test_range}...")
        result = sheets.spreadsheets().values().append(
            spreadsheetId=Config.GOOGLE_SHEET_ID,
            range=test_range,
            valueInputOption='RAW',
            body=body
        ).execute()
        
        print("✅ 寫入成功！")
        print(f"詳細回傳: {result}")
        
    except Exception as e:
        print(f"❌ 診斷失敗: {str(e)}")

if __name__ == "__main__":
    diagnostic_sheet()
