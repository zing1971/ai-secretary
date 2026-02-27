import os
from dotenv import load_dotenv
from google_auth import get_google_services
from gmail_service import get_recent_emails
from calendar_service import get_todays_events
from llm_service import generate_report
from line_service import send_line_message

def main():
    # 1. 載入環境變數（強制覆蓋系統現有變數）
    load_dotenv(override=True)
    
    # 2. 取得 Google 服務
    try:
        gmail_service, calendar_service = get_google_services()
    except Exception as e:
        print(f"Google 驗證失敗: {e}")
        return

    # 3. 抓取資料
    print("正在抓取今日行程與新信件...")
    events = get_todays_events(calendar_service)
    emails = get_recent_emails(gmail_service)

    # 4. AI 生成報告
    print("正在由 AI 秘書擬定匯報內容...")
    prompt_path = "ai_prompt_draft.md"
    try:
        report = generate_report(events, emails, prompt_path)
    except Exception as e:
        print(f"AI 生成匯報失敗: {e}")
        return

    # 5. 推送至 Line
    print("正在發送 Line 匯報...")
    send_line_message(report)
    
    print("任務完成！")

if __name__ == "__main__":
    main()
