"""
AI Secretary - 主程式入口
核心原則：先讓 uvicorn 綁定 8080 埠口，再背景初始化所有服務。
絕不在模組頂層做任何可能失敗的操作。
"""
import asyncio
import os
import sys
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
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, PlainTextResponse, JSONResponse
from contextlib import asynccontextmanager


# 全域狀態
class _State:
    line_service = None
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
        from line_service import LineService
        from google_auth import get_google_services
        from llm_service import LLMService
        from intent_router import IntentRouter
        from action_dispatcher import ActionDispatcher

        Config.validate()

        S.line_service = LineService()
        register_line_handlers(S.line_service)
        logger.info("✅ LINE 服務就緒")

        S.llm_service = LLMService(Config.GEMINI_API_KEY)
        S.intent_router = IntentRouter(Config.GEMINI_API_KEY)
        logger.info("✅ AI 服務就緒")

        gmail, calendar, tasks, sheets, drive = get_google_services()
        logger.info("✅ Google 服務就緒")

        S.dispatcher = ActionDispatcher(
            S.line_service, S.llm_service,
            gmail, calendar, tasks, sheets, drive
        )
        logger.info("✅ Dispatcher 就緒")

        S.ready = True
        logger.info("🎉 AI 秘書完全上線！")

    except Exception as e:
        logger.error(f"❌ 初始化失敗: {e}", exc_info=True)


app = FastAPI(title="AI Secretary", lifespan=lifespan)


# ===== 路由 =====

@app.get("/", response_class=HTMLResponse)
async def root():
    status = "🟢 Alice 在線服務中" if S.ready else "🟡 Alice 正在準備中..."
    return f"""<html><body style="font-family:Arial;text-align:center;padding:50px">
    <h1>👩‍💼 AI 秘書 Alice ({status})</h1></body></html>"""


@app.post("/callback")
async def callback(request: Request):
    """LINE Webhook"""
    signature = request.headers.get("X-Line-Signature", "")
    body = await request.body()
    body_str = body.decode("utf-8")

    if not S.ready or not S.line_service:
        logger.warning("Webhook 收到請求但服務還沒就緒，先回 OK 不處理。")
        return PlainTextResponse("OK")

    try:
        S.line_service.handler.handle(body_str, signature)
    except Exception as e:
        logger.error(f"Webhook 處理異常: {e}")
        return PlainTextResponse("OK")

    return PlainTextResponse("OK")


# ===== 新增：Cloud Scheduler 觸發的每日簡報端點 =====

@app.post("/trigger-briefing")
async def trigger_briefing(request: Request):
    """
    由 Google Cloud Scheduler 定時呼叫的端點。
    觸發每日早安簡報流程：讀取行程 + 信件 → AI 分析 → 推送到 LINE。
    """
    logger.info("📩 收到簡報觸發請求")

    if not S.ready or not S.dispatcher:
        logger.warning("服務尚未就緒，無法執行簡報。")
        return JSONResponse(
            status_code=503,
            content={"status": "error", "message": "服務尚未就緒"}
        )

    try:
        # 執行主動處理流程
        report = S.dispatcher.handle_proactive_process()

        # 組合並推送訊息
        push_msg = f"🌅 仁哥早安！以下是 Alice 為您準備的今日簡報：\n{report}"
        S.line_service.push_text(push_msg)

        logger.info("✅ 早安簡報推送成功！")
        return JSONResponse(content={"status": "ok", "message": "簡報已推送"})

    except Exception as e:
        logger.error(f"❌ 簡報執行失敗: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": str(e)}
        )


@app.get("/trigger-briefing")
async def trigger_briefing_get():
    """GET 方法用於手動測試"""
    if not S.ready or not S.dispatcher:
        return JSONResponse(
            status_code=503,
            content={"status": "error", "message": "服務尚未就緒"}
        )

    try:
        report = S.dispatcher.handle_proactive_process()
        push_msg = f"🌅 仁哥早安！以下是 Alice 為您準備的今日簡報：\n{report}"
        S.line_service.push_text(push_msg)
        return JSONResponse(content={"status": "ok", "message": "簡報已推送"})
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": str(e)}
        )


@app.post("/trigger-drive-organize")
async def trigger_drive_organize():
    """Cloud Scheduler 定期觸發 Drive 整理掃描"""
    if not S.ready or not S.dispatcher:
        return JSONResponse(
            status_code=503,
            content={"status": "error", "message": "服務尚未就緒"}
        )

    try:
        user_id = S.line_service.user_id
        if S.dispatcher.drive_organizer:
            result = S.dispatcher.drive_organizer.scan_and_propose(user_id)
            S.line_service.push_text(result)
            logger.info("✅ Drive 整理提案已推送")
            return JSONResponse(content={"status": "ok", "message": "提案已推送"})
        else:
            return JSONResponse(
                status_code=503,
                content={"status": "error", "message": "Drive 服務未就緒"}
            )
    except Exception as e:
        logger.error(f"❌ Drive 整理觸發失敗: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": str(e)}
        )


@app.get("/trigger-drive-organize")
async def trigger_drive_organize_get():
    """GET 方法用於手動測試"""
    return await trigger_drive_organize()


# ===== LINE 訊息處理 =====

def register_line_handlers(line_svc):
    """註冊 LINE 事件處理函數"""
    from linebot.models import MessageEvent, TextMessage

    @line_svc.handler.add(MessageEvent, message=TextMessage)
    def handle_message(event):
        user_id = event.source.user_id
        user_message = event.message.text.strip()

        logger.info(f"收到訊息: {user_message} (from {user_id})")

        if not S.ready:
            S.line_service.reply_text(event.reply_token, "仁哥，Alice 正在開機中，請稍等一下喔 ☕")
            return

        if user_id != S.line_service.user_id:
            return

        # 手動測試簡報指令
        if user_message == "測試排程":
            try:
                report = S.dispatcher.handle_proactive_process()
                push_msg = f"🌅 仁哥早安！以下是 Alice 為您準備的簡報：\n{report}"
                S.line_service.reply_text(event.reply_token, push_msg)
            except Exception as e:
                S.line_service.reply_text(event.reply_token, f"仁哥抱歉，Alice 執行簡報時遇到問題：{e} 🙇‍♀️")
            return

        # 常規意圖分析與分派
        analysis_result = S.intent_router.classify_intent(user_message)
        intent = analysis_result.get("intent", "Chat")
        S.dispatcher.dispatch(intent, user_message, user_id, reply_token=event.reply_token)


# ===== 啟動入口 =====
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8080"))
    uvicorn.run(app, host="0.0.0.0", port=port)
