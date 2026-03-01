import os
import json
import subprocess
from google_auth import get_google_services

def update_cloud_run(token_json_str):
    """使用 gcloud 指令更新 Cloud Run 的環境變數"""
    print("☁️ 正在更新 Cloud Run 環境變數...")
    service_name = "ai-secretary"
    region = "asia-east1"
    
    # 建立指令 (在 Windows 下執行 gcloud 可能需要 shell=True)
    command = [
        "gcloud", "run", "services", "update", service_name,
        "--platform", "managed",
        "--region", region,
        "--set-env-vars", f"GOOGLE_TOKEN_JSON='{token_json_str}'"
    ]
    
    try:
        # 執行指令
        # Windows 上調用 gcloud (通常是 gcloud.cmd) 需要 shell=True
        result = subprocess.run(" ".join(command), shell=True, capture_output=True, text=True, check=True)
        print("✅ Cloud Run 環境變數已成功更新！")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ 更新 Cloud Run 失敗: {e.stderr}")
        return False

def main():
    print("🚀 準備更新 Google 授權 (包含聯絡人權限) 並同步至雲端")
    
    # 1. 刪除舊的 token
    if os.path.exists('token.json'):
        print("🗑️ 刪除舊的 token.json")
        os.remove('token.json')
        
    print("🌐 即將開啟瀏覽器，請登入並同意所有權限要求 (包含 Google Contacts)...")
    
    try:
        # 2. 觸發登入流程
        get_google_services()
        
        if not os.path.exists('token.json'):
            print("❌ 未能成功生成 token.json，請檢查登入流程。")
            return

        print("\n✅ 新的 token.json 已成功生成！")
        
        # 3. 讀取新的 token 內容
        with open('token.json', 'r') as f:
            token_data = f.read()
        
        # 4. 自動同步到 Cloud Run
        success = update_cloud_run(token_data)
        
        if success:
            print("\n🎉 全部完成！")
        else:
            print("\n⚠️ 授權已更新，但 Cloud Run 同步失敗。")
            print("請手動複製以下 token.json 內容至 GCP 控制台 GOOGLE_TOKEN_JSON 環境變數中：")
            print("-" * 30)
            print(token_data)
            print("-" * 30)
            
        print("\n現在您可以執行 ./deploy.sh 部署最新程式碼了。")

    except Exception as e:
        print(f"\n❌ 發生錯誤: {e}")

if __name__ == "__main__":
    main()
