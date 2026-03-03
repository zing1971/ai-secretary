import sys
import os

# 加入專案目錄到路徑
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from google_auth import get_google_services
from drive_service import DriveService
from config import logger

def test_search_drive():
    services = get_google_services()
    drive_api = services[4]  # drive_service is the 5th element returned
    
    if not drive_api:
        print("沒有有效的 Google Drive API 憑證")
        return

    drive_service = DriveService(drive_api)

    # 測試搜尋關鍵字 "測試"
    test_keyword = "測試"
    print(f"🔍 開始測試 Drive 搜尋，關鍵字：'{test_keyword}'")
    
    files = drive_service.search_files_by_keyword(test_keyword, max_results=5)
    
    print(f"✅ 搜尋完成，共找到 {len(files)} 個檔案：")
    for idx, f in enumerate(files, 1):
        print(f"  {idx}. {f.get('name')} (類型: {f.get('mimeType')})")
        print(f"     連結: {f.get('webViewLink')}")
        print(f"     時間: {f.get('modifiedTime')}")

if __name__ == "__main__":
    test_search_drive()
