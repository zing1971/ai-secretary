import os
from google_auth import get_google_services, SCOPES

def main():
    print("🚀 準備更新 Google 授權 (新增聯絡人權限)")
    
    if os.path.exists('token.json'):
        print("🗑️ 刪除舊的 token.json")
        os.remove('token.json')
        
    print("🌐 即將開啟瀏覽器，請同意所有權限要求 (包含 Google Contacts)")
    
    try:
        # 呼叫 get_google_services 會自動觸發登入流程並產生新的 token.json
        get_google_services()
        print("\n✅ 新的 token.json 已成功生成！")
        
        with open('token.json', 'r') as f:
            token_data = "".join(f.readlines())
        
        print("\n=== 請複製以下內容，更新到 Cloud Run 的 GOOGLE_TOKEN_JSON 表單中 ===")
        print(token_data)
        print("=======================================================================")
        
    except Exception as e:
        print(f"\n❌ 產生授權失敗: {e}")

if __name__ == "__main__":
    main()
