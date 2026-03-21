"""
AI Secretary - 主程式入口（Telegram 版）
核心原則：先讓 uvicorn 綁定 8080 埠口，再背景初始化所有服務。
絕不在模組頂層做任何可能失敗的操作。
"""
import asyncio
import os
import sys
import json
import logging

# ===== 第一步：最基礎的 Logging（零依賴）=====
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("AI-Secretary")
logger.info(f"🔧 Python {sys.version}")
logger.info(f"🔧 PORT={os.getenv('PORT', '8080')}")

# ===== 第二步：建立 FastAPI 應用（極輕量）=====
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, JSONResponse
from contextlib import asynccontextmanager


# 全域狀態
class _State:
    tg_service = None
    llm_service = None
    intent_router = None
    dispatcher = None
    ready = False

S = _State()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """伺服器已綁定埠口後才執行的生命週期"""
    logger.info("🚀 伺服器已啟動，開始背景初始化服務...")
    asyncio.create_task(_initialize_all_services(app))
    yield
    logger.info("🛑 伺服器關閉中...")


async def _initialize_all_services(app):
    """背景初始化所有服務（不阻塞 8080 埠口）"""
    try:
        from config import Config
        from telegram_service import TelegramService
        from google_auth import get_google_services
        from llm_service import LLMService
        from intent_router import IntentRouter
        from role_dispatcher import RoleDispatcher

        Config.validate()

        S.tg_service = TelegramService()
        logger.info("✅ Telegram 服務就緒")

        S.llm_service = LLMService(Config.GEMINI_API_KEY)
        S.intent_router = IntentRouter(Config.GEMINI_API_KEY)
        logger.info("✅ AI 服務就緒")

        gmail, calendar, tasks, sheets, drive, people = get_google_services()
        logger.info("✅ Google 服務就緒")

        S.dispatcher = RoleDispatcher(
            S.tg_service, S.llm_service,
            gmail, calendar, tasks, sheets, drive, people
        )
        logger.info("✅ 雙角色分流器就緒（Alice + Birdie）")

        S.ready = True
        logger.info("🎉 AI 秘書完全上線！")

    except Exception as e:
        logger.error(f"❌ 初始化失敗: {e}", exc_info=True)


app = FastAPI(title="AI Secretary (Telegram)", lifespan=lifespan)


# ===== 路由 =====

@app.get("/", response_class=HTMLResponse)
async def root():
    status = "🟢 Alice 在線服務中" if S.ready else "🟡 Alice 正在準備中..."
    return f"""<html><body style="font-family:Arial;text-align:center;padding:50px">
    <h1>👩‍💼 AI 秘書 Alice ({status})</h1></body></html>"""


@app.post("/webhook")
async def webhook(request: Request):
    """Telegram Webhook — 處理所有來自 Telegram 的 Update"""
    try:
        body = await request.json()
    except Exception:
        return PlainTextResponse("OK")

    if not S.ready or not S.tg_service:
        logger.warning("Webhook 收到請求但服務還沒就緒，忽略。")
        return PlainTextResponse("OK")

    try:
        await _handle_update(body)
    except Exception as e:
        logger.error(f"Webhook 處理異常: {e}", exc_info=True)

    return PlainTextResponse("OK")


async def _handle_update(update: dict):
    """解析 Telegram Update 並分派至 dispatcher"""

    # ── 一般文字訊息 ──────────────────────────────────────────────
    message = update.get("message")
    if message:
        chat_id = str(message["chat"]["id"])
        reply_token = chat_id  # Telegram 無 reply_token，以 chat_id 代替

        # 安全過濾：只處理指定的使用者
        if chat_id != S.tg_service.chat_id:
            logger.warning(f"忽略非授權 chat_id: {chat_id}")
            return

        # 文字訊息
        if "text" in message:
            user_message = message["text"].strip()
            logger.info(f"收到文字訊息: {user_message}")

            # 顯示主選單指令
            if user_message in ("/start", "/menu", "選單", "menu"):
                S.tg_service.send_main_menu(chat_id)
                return

            # 手動測試簡報指令
            if user_message == "測試排程":
                try:
                    report = S.dispatcher.handle_proactive_process()
                    push_msg = f"🌅 仁哥早安！以下是 Alice 為您準備的簡報：\n{report}"
                    S.tg_service.reply_text(reply_token, push_msg)
                except Exception as e:
                    S.tg_service.reply_text(reply_token, f"仁哥抱歉，Alice 執行簡報時遇到問題：{e} 🙇‍♀️")
                return

            # 常規意圖分析與分派
            analysis_result = S.intent_router.classify_intent(user_message)
            S.dispatcher.dispatch(analysis_result, user_message, chat_id, reply_token=reply_token)

        # 圖片訊息
        elif "photo" in message:
            # 取最高解析度的圖片（最後一張）
            file_id = message["photo"][-1]["file_id"]
            logger.info(f"收到圖片訊息 (file_id: {file_id})")
            image_bytes = S.tg_service.get_message_content(file_id)
            if image_bytes:
                S.dispatcher.dispatch_image(image_bytes, chat_id, reply_token=reply_token)
            else:
                S.tg_service.reply_text(reply_token, "仁哥抱歉，Alice 無法讀取這張圖片 🙇‍♀️")

    # ── Inline Keyboard 回調（快捷選單按鈕）─────────────────────────
    callback_query = update.get("callback_query")
    if callback_query:
        chat_id = str(callback_query["message"]["chat"]["id"])
        callback_data = callback_query.get("data", "")
        callback_id = callback_query.get("id")

        if chat_id != S.tg_service.chat_id:
            return

        logger.info(f"收到 Callback Query: {callback_data}")

        # 回答 callback query（消除 loading 動畫）
        try:
            import requests as req
            req.post(
                f"https://api.telegram.org/bot{S.tg_service.token}/answerCallbackQuery",
                json={"callback_query_id": callback_id},
                timeout=5
            )
        except Exception:
            pass

        # 將按鈕文字內容當成一般訊息處理
        analysis_result = S.intent_router.classify_intent(callback_data)
        S.dispatcher.dispatch(analysis_result, callback_data, chat_id, reply_token=chat_id)


# ===== Cloud Scheduler 觸發的每日簡報端點 =====

@app.post("/trigger-briefing")
async def trigger_briefing(request: Request):
    """由 Google Cloud Scheduler 定時呼叫的端點"""
    logger.info("📩 收到簡報觸發請求")
    if not S.ready or not S.dispatcher:
        return JSONResponse(status_code=503, content={"status": "error", "message": "服務尚未就緒"})
    try:
        report = S.dispatcher.handle_proactive_process()
        push_msg = f"🌅 仁哥早安！以下是 Alice 為您準備的今日簡報：\n{report}"
        S.tg_service.push_text(push_msg)
        logger.info("✅ 早安簡報推送成功！")
        return JSONResponse(content={"status": "ok", "message": "簡報已推送"})
    except Exception as e:
        logger.error(f"❌ 簡報執行失敗: {e}", exc_info=True)
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})


@app.get("/trigger-briefing")
async def trigger_briefing_get():
    """GET 方法用於手動測試"""
    if not S.ready or not S.dispatcher:
        return JSONResponse(status_code=503, content={"status": "error", "message": "服務尚未就緒"})
    try:
        report = S.dispatcher.handle_proactive_process()
        push_msg = f"🌅 仁哥早安！以下是 Alice 為您準備的今日簡報：\n{report}"
        S.tg_service.push_text(push_msg)
        return JSONResponse(content={"status": "ok", "message": "簡報已推送"})
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})


@app.post("/trigger-drive-organize")
async def trigger_drive_organize():
    """Cloud Scheduler 定期觸發 Drive 整理掃描"""
    if not S.ready or not S.dispatcher:
        return JSONResponse(status_code=503, content={"status": "error", "message": "服務尚未就緒"})
    try:
        user_id = S.tg_service.chat_id
        if S.dispatcher.drive_organizer:
            result = S.dispatcher.drive_organizer.scan_and_propose(user_id)
            S.tg_service.push_text(result)
            logger.info("✅ Drive 整理提案已推送")
            return JSONResponse(content={"status": "ok", "message": "提案已推送"})
        else:
            return JSONResponse(status_code=503, content={"status": "error", "message": "Drive 服務未就緒"})
    except Exception as e:
        logger.error(f"❌ Drive 整理觸發失敗: {e}", exc_info=True)
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})


@app.get("/trigger-drive-organize")
async def trigger_drive_organize_get():
    """GET 方法用於手動測試"""
    return await trigger_drive_organize()


# ===== Telegram Webhook 設定輔助端點 =====

@app.get("/setup-webhook")
async def setup_webhook(request: Request):
    """
    一次性呼叫此端點，即可自動將 Telegram Webhook 指向目前服務的 URL。
    用法：瀏覽器開啟 https://<your-cloud-run-url>/setup-webhook
    """
    from config import Config
    import requests as req

    host = str(request.base_url).rstrip("/")
    webhook_url = f"{host}/webhook"

    resp = req.post(
        f"https://api.telegram.org/bot{Config.TELEGRAM_BOT_TOKEN}/setWebhook",
        json={"url": webhook_url},
        timeout=15
    )
    result = resp.json()
    logger.info(f"setWebhook 結果: {result}")
    if result.get("ok"):
        return JSONResponse(content={"status": "ok", "webhook_url": webhook_url, "result": result})
    else:
        return JSONResponse(status_code=500, content={"status": "error", "result": result})


# ===== 啟動入口 =====
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8080"))
    uvicorn.run(app, host="0.0.0.0", port=port)
