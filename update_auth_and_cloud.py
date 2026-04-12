"""
Google OAuth Token 更新腳本（本地執行）

用法：
1. 在本機（有瀏覽器的電腦）執行此腳本
2. 完成 Google 登入後，腳本會自動將 token.json 上傳到 VPS

前置條件：
- 本機有 credentials.json
- SSH 已設定好連線至 VPS（金鑰登入）
"""
import os
import sys
import subprocess
from google_auth import get_google_services


# ── 請修改為您的 VPS 設定 ──────────────────────────────────
VPS_USER = "root"               # VPS 使用者名稱
VPS_HOST = "your-vps-ip"        # VPS IP 或主機名
VPS_APP_DIR = "~/ai-secretary"  # VPS 上的專案目錄
# ──────────────────────────────────────────────────────────


def main():
    print("🚀 準備更新 Google 授權 Token 並同步至 VPS")

    # 1. 刪除舊的 token
    if os.path.exists('token.json'):
        print("🗑️ 刪除舊的 token.json")
        os.remove('token.json')

    print("🌐 即將開啟瀏覽器，請登入並同意所有權限要求...")

    try:
        # 2. 觸發登入流程（會開瀏覽器）
        get_google_services()

        if not os.path.exists('token.json'):
            print("❌ 未能成功生成 token.json，請檢查登入流程。")
            return

        print("\n✅ 新的 token.json 已成功生成！")

        # 3. 上傳到 VPS
        if VPS_HOST == "your-vps-ip":
            print("\n⚠️ 尚未設定 VPS 連線資訊！")
            print("   請編輯此腳本頂部的 VPS_USER / VPS_HOST / VPS_APP_DIR")
            print("   或手動上傳：")
            print(f"   scp token.json {VPS_USER}@{VPS_HOST}:{VPS_APP_DIR}/")
            return

        print(f"\n📤 上傳 token.json 至 {VPS_USER}@{VPS_HOST}...")
        scp_cmd = f"scp token.json {VPS_USER}@{VPS_HOST}:{VPS_APP_DIR}/"
        result = subprocess.run(scp_cmd, shell=True)

        if result.returncode == 0:
            print("✅ token.json 已成功上傳至 VPS！")

            # 4. 重啟 VPS 上的服務
            print("🔄 重啟 VPS 上的 ai-secretary 服務...")
            restart_cmd = f'ssh {VPS_USER}@{VPS_HOST} "sudo systemctl restart ai-secretary"'
            subprocess.run(restart_cmd, shell=True)
            print("🎉 全部完成！服務已重新啟動。")
        else:
            print("❌ SCP 上傳失敗，請檢查 SSH 連線設定。")
            print(f"   手動上傳：scp token.json {VPS_USER}@{VPS_HOST}:{VPS_APP_DIR}/")

    except Exception as e:
        print(f"\n❌ 發生錯誤: {e}")


if __name__ == "__main__":
    main()
