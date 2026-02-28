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
from fastapi.responses import HTMLResponse, PlainTextResponse
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
    if hasattr(app.state, 'scheduler'):
        app.state.scheduler.shutdown()


async def _initialize_all_services(app):
    """背景初始化所有服務（不阻塞 8080 埠口）"""
    try:
        # 在這裡才開始 import 重型模組
        from config import Config
        from line_service import LineService
        from google_auth import get_google_services
        from llm_service import LLMService
        from intent_router import IntentRouter
        from action_dispatcher import ActionDispatcher
        from scheduler_service import setup_scheduler

        Config.validate()

        S.line_service = LineService()
        register_line_handlers(S.line_service)
        logger.info("✅ LINE 服務就緒")

        S.llm_service = LLMService(Config.GEMINI_API_KEY)
        S.intent_router = IntentRouter(Config.GEMINI_API_KEY)
        logger.info("✅ AI 服務就緒")

        gmail, calendar, tasks, sheets = get_google_services()
        logger.info("✅ Google 服務就緒")

        S.dispatcher = ActionDispatcher(
            S.line_service, S.llm_service,
            gmail, calendar, tasks, sheets
        )
        logger.info("✅ Dispatcher 就緒")

        try:
            scheduler = setup_scheduler(S.line_service.api, S.line_service.user_id)
            app.state.scheduler = scheduler
            logger.info("✅ 排程器就緒")
        except Exception as e:
            logger.warning(f"⚠️ 排程器啟動失敗: {e}")

        S.ready = True
        logger.info("🎉 AI 秘書完全上線！")

    except Exception as e:
        logger.error(f"❌ 初始化失敗: {e}", exc_info=True)


app = FastAPI(title="AI Secretary", lifespan=lifespan)


# ===== 路由 =====

@app.get("/", response_class=HTMLResponse)
async def root():
    status = "🟢 正常運行" if S.ready else "🟡 啟動中"
    return f"""<html><body style="font-family:Arial;text-align:center;padding:50px">
    <h1>🤖 AI 秘書 ({status})</h1></body></html>"""


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
        # LINE 需要收到 200，不然會重試
        return PlainTextResponse("OK")

    return PlainTextResponse("OK")


def register_line_handlers(line_svc):
    """註冊 LINE 事件處理函數"""
    from linebot.models import MessageEvent, TextMessage

    @line_svc.handler.add(MessageEvent, message=TextMessage)
    def handle_message(event):
        user_id = event.source.user_id
        user_message = event.message.text.strip()

        logger.info(f"收到訊息: {user_message} (from {user_id})")

        if not S.ready:
            S.line_service.reply_text(event.reply_token, "秘書正在開機中，請稍後再試。")
            return

        if user_id != S.line_service.user_id:
            return

        if user_message == "測試排程":
            from scheduler_service import send_morning_briefing
            asyncio.create_task(send_morning_briefing(S.line_service.api, user_id))
            S.line_service.reply_text(event.reply_token, "好的老闆，正在執行簡報測試...")
            return

        analysis_result = S.intent_router.classify_intent(user_message)
        intent = analysis_result.get("intent", "Chat")
        S.dispatcher.dispatch(intent, user_message, user_id, reply_token=event.reply_token)


# ===== 啟動入口 =====
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8080"))
    uvicorn.run(app, host="0.0.0.0", port=port)
