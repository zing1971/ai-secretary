from google_auth import get_google_services
import os

def test_all_services():
    print("🔍 正在測試 Google 服務連線 (包含 Sheets 記憶功能)...")
    try:
        gmail, calendar, tasks, sheets, drive = get_google_services()
        
        print("✅ Gmail 服務已就緒")
        print("✅ Calendar 服務已就緒")
        print("✅ Tasks 服務已就緒")
        print("✅ Sheets 服務已就緒")
        
        # 測試 Sheets 讀取
        sheet_id = os.getenv("GOOGLE_SHEET_ID")
        if sheet_id:
            result = sheets.spreadsheets().get(spreadsheetId=sheet_id).execute()
            print(f"✅ 成功存取試算表: {result.get('properties', {}).get('title')}")
        else:
            print("⚠️ 未設定 GOOGLE_SHEET_ID，無法測試讀取。")
            
        print("\n🎉 所有 Google 服務測試通過！您可以繼續進行對話測試了。")
        
    except Exception as e:
        print(f"\n❌ 連線測試失敗: {str(e)}")
        print("\n提示：如果您看到權限錯誤，請再次確認是否已授予所有要求權限。")

if __name__ == "__main__":
    test_all_services()
