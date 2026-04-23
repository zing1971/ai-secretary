"""
排程服務工具模組

注意：Cloud Run 環境下不使用 APScheduler（容器會休眠）。
改由 Google Cloud Scheduler 定時呼叫 /trigger-briefing 端點。

此模組僅保留簡報邏輯函數，供 app.py 直接呼叫或本地測試使用。
"""
import logging

logger = logging.getLogger("AI-Secretary")


def execute_morning_briefing(dispatcher, messaging_service):
    """
    執行早安簡報的核心邏輯。
    
    Args:
        dispatcher: RoleDispatcher 實例
        messaging_service: TelegramService 或 LineService 實例
    
    Returns:
        str: 簡報內容
    """
    try:
        report = dispatcher.handle_proactive_process()
        push_msg = f"🌅 【早安簡報】\n{report}"
        messaging_service.push_text(push_msg)
        
        # 傳送早安簡報情境選單 (若服務端支援)
        if hasattr(messaging_service, 'send_context_menu'):
            messaging_service.send_context_menu("morning_briefing")
            
        # 將簡報寫入 SOUL.md，讓 Hermes Agent 擁有上下文
        import os
        from datetime import datetime
        soul_path = os.path.expanduser("~/.hermes/SOUL.md")
        if os.path.exists(soul_path):
            try:
                with open(soul_path, "a", encoding="utf-8") as f:
                    today = datetime.now().strftime("%Y-%m-%d %H:%M")
                    f.write(f"\n\n---\n**系統紀錄 ({today})：已向使用者發送早安簡報**\n簡報內容如下：\n{report}\n")
                logger.info("💾 已將早安簡報注入 SOUL.md 上下文")
            except Exception as io_err:
                logger.warning(f"寫入 SOUL.md 失敗: {io_err}")

        logger.info("✅ 早安簡報推送成功！")
        return push_msg
    except Exception as e:
        logger.error(f"❌ 早安簡報執行失敗: {e}")
        raise
