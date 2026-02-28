from config import logger
from google_auth import get_google_services
from gmail_service import get_recent_emails
from calendar_service import get_todays_events
from llm_service import llm_service
from line_service import line_service

def main():
    logger.info("正在執行 CLI 模式手動匯報任務...")
    
    # 1. 取得 Google 服務
    try:
        gmail_service, calendar_service, _ = get_google_services()
    except Exception as e:
        logger.error(f"Google 驗證失敗: {e}")
        return

    # 2. 抓取資料
    logger.info("正在抓取今日行程與新信件...")
    events = get_todays_events(calendar_service)
    emails_raw = get_recent_emails(gmail_service)
    emails = [e['summary_text'] for e in emails_raw]

    # 3. AI 生成報告
    logger.info("正在由 AI 秘書擬定匯報內容...")
    prompt_path = "ai_prompt_draft.md"
    try:
        with open(prompt_path, "r", encoding="utf-8") as f:
            system_prompt = f.read()
        
        report = llm_service.generate_report(events, emails, system_prompt)
    except Exception as e:
        logger.error(f"AI 生成匯報失敗: {e}")
        return

    # 4. 推送至 Line
    logger.info("正在發送 Line 匯報...")
    line_service.push_text(report)
    
    logger.info("CLI 任務執行成功！")

if __name__ == "__main__":
    main()
