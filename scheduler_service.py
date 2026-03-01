"""
排程服務工具模組

注意：Cloud Run 環境下不使用 APScheduler（容器會休眠）。
改由 Google Cloud Scheduler 定時呼叫 /trigger-briefing 端點。

此模組僅保留簡報邏輯函數，供 app.py 直接呼叫或本地測試使用。
"""
import logging

logger = logging.getLogger("AI-Secretary")


def execute_morning_briefing(dispatcher, line_service):
    """
    執行早安簡報的核心邏輯。
    
    Args:
        dispatcher: ActionDispatcher 實例
        line_service: LineService 實例
    
    Returns:
        str: 簡報內容
    """
    try:
        report = dispatcher.handle_proactive_process()
        push_msg = f"🌅 【早安簡報】\n{report}"
        line_service.push_text(push_msg)
        logger.info("✅ 早安簡報推送成功！")
        return push_msg
    except Exception as e:
        logger.error(f"❌ 早安簡報執行失敗: {e}")
        raise
