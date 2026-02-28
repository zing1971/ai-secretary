from google_auth import get_google_services
from tasks_service import create_google_task
from gmail_service import create_gmail_draft
import os

def run_smoke_test():
    print("🚀 啟動 AI 秘書連線冒煙測試...")
    
    # 檢查 Token 是否存在，若不存在提醒使用者需要互動授權
    if not os.path.exists('token.json'):
        print("⚠️ 找不到 token.json，系統將會開啟瀏覽器要求領取新授權。")
        print("請確保您在圖形化介面（螢幕前）操作，或先執行 python app.py 完成授權。")

    try:
        gmail, cal, tasks = get_google_services()
        
        print("\n[測試 1] 建立 Google Tasks 任務...")
        task_title = "🤖 AI 秘書連線驗證任務"
        task_notes = "如果您在 Task 清單看到這個項目，代表連線成功！"
        task_id = create_google_task(tasks, task_title, task_notes)
        print(f"✅ 成功：已建立任務 (ID: {task_id})")
        
        print("\n[測試 2] 建立 Gmail 回覆草稿...")
        draft_to = "test@example.com"
        draft_subject = "📩 AI 秘書連線驗證草稿"
        draft_body = "這是一封由測試腳本自動生成的草稿。若您在 Gmail 草稿匣看到它，代表連線成功！"
        draft_id = create_gmail_draft(gmail, draft_to, draft_subject, draft_body)
        print(f"✅ 成功：已建立草稿 (ID: {draft_id})")
        
        print("\n🎉 所有服務連線測試完成！請到您的 Google 帳戶檢查結果。")
        
    except Exception as e:
        print(f"\n❌ 測試發生錯誤: {e}")

if __name__ == "__main__":
    run_smoke_test()
