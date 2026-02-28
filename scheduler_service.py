from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz
from datetime import datetime
import os
from google_auth import get_google_services
from calendar_service import get_todays_events
from gmail_service import get_recent_emails, create_gmail_draft
from tasks_service import create_google_task
from llm_service import analyze_for_actions

# 設定時區
TIMEZONE = pytz.timezone('Asia/Taipei')

async def send_morning_briefing(line_bot_api, user_id):
    """執行早晨簡報任務。"""
    print(f"[{datetime.now(TIMEZONE)}] 開始執行定時早晨簡報...")
    
    try:
        # 1. 取得服務
        gmail_service, calendar_service, tasks_service = get_google_services()
        
        if not gmail_service or not calendar_service or not tasks_service:
            print("Google 服務授權不全，取消簡報。")
            return

        # 2. 抓取資料
        events = get_todays_events(calendar_service)
        emails = get_recent_emails(gmail_service)
        
        # 3. AI 分析
        action_data = analyze_for_actions(events, emails)
        
        # 4. 執行自動化動作 (與 app.py 邏輯一致)
        tasks_created = 0
        for task in action_data.get('tasks', []):
            create_google_task(tasks_service, task.get('title'), task.get('notes'), task.get('due'))
            tasks_created += 1
            
        drafts_created = 0
        for draft in action_data.get('drafts', []):
            create_gmail_draft(gmail_service, draft.get('to'), draft.get('subject'), draft.get('body'), draft.get('threadId'))
            drafts_created += 1
            
        # 5. 組合推送訊息
        briefing = action_data.get('briefing', '老闆，這是您今天的簡報。')
        push_msg = f"🌅 【早安簡報】\n\n{briefing}\n\n✅ 已自動為您建立 {tasks_created} 項待辦事項\n✉️ 已擬好 {drafts_created} 封郵件草稿"
        
        # 6. 推送到 LINE
        from linebot.models import TextSendMessage
        line_bot_api.push_message(user_id, TextSendMessage(text=push_msg))
        print("早晨簡報推送成功！")
        
    except Exception as e:
        print(f"執行定時簡報時發生錯誤: {e}")

def setup_scheduler(line_bot_api, user_id):
    """初始化並啟動排程器。"""
    scheduler = AsyncIOScheduler(timezone=TIMEZONE)
    
    # 設定每天早上 7:00 執行
    # 您也可以在這裡修改時間，或是加入多個任務
    scheduler.add_job(
        send_morning_briefing,
        CronTrigger(hour=7, minute=0),
        args=[line_bot_api, user_id],
        id='morning_briefing',
        name='Daily Morning Briefing',
        replace_existing=True
    )
    
    # 測試用：每 5 分鐘跑一次（可選）
    # scheduler.add_job(send_morning_briefing, 'interval', minutes=5, args=[line_bot_api, user_id])
    
    scheduler.start()
    print("排程器已啟動，目標時間：每日 07:00")
    return scheduler
