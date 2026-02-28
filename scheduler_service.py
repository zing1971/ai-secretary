from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz
from datetime import datetime

from config import logger
from google_auth import get_google_services
from action_dispatcher import ActionDispatcher

# 設定時區
TIMEZONE = pytz.timezone('Asia/Taipei')

async def send_morning_briefing(line_bot_api, user_id):
    """執行早晨簡報任務。"""
    logger.info(f"[{datetime.now(TIMEZONE)}] 開始執行定時早晨簡報任務...")
    
    try:
        # 1. 取得服務
        gmail_service, calendar_service, tasks_service = get_google_services()
        
        if not all([gmail_service, calendar_service, tasks_service]):
            logger.warning("Google 服務授權不全，取消簡報。")
            return

        # 2. 使用 Dispatcher 處理主動流程 (共用邏輯)
        dispatcher = ActionDispatcher()
        report = dispatcher.handle_proactive_process(gmail_service, calendar_service, tasks_service)
        
        # 3. 組合推送訊息
        push_msg = f"🌅 【早安簡報】\n{report}"
        
        # 4. 推送到 LINE
        from linebot.models import TextSendMessage
        line_bot_api.push_message(user_id, TextSendMessage(text=push_msg))
        logger.info("早晨簡報推送成功！")
        
    except Exception as e:
        logger.error(f"執行定時簡報時發生錯誤: {e}")

def setup_scheduler(line_bot_api, user_id):
    """初始化並啟動排程器。"""
    scheduler = AsyncIOScheduler(timezone=TIMEZONE)
    
    # 設定每天早上 7:00 執行
    scheduler.add_job(
        send_morning_briefing,
        CronTrigger(hour=7, minute=0),
        args=[line_bot_api, user_id],
        id='morning_briefing',
        name='Daily Morning Briefing',
        replace_existing=True
    )
    
    scheduler.start()
    logger.info("排程器已啟動，目標時間：每日 07:00 (Taipei)")
    return scheduler
