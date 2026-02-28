import asyncio
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage
from contextlib import asynccontextmanager

from config import Config, logger
from line_service import LineService
from google_auth import get_google_services
from llm_service import LLMService
from intent_router import IntentRouter
from action_dispatcher import ActionDispatcher
from scheduler_service import setup_scheduler, send_morning_briefing

# --- 非同步初始化全域服務 (延遲啟動關鍵服務) ---
line_service = LineService()
# 此處不直接初始化需要 API 金鑰的服務，改到 lifespan 或初次使用時
llm_service = None
intent_router = None
global_dispatcher = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global llm_service, intent_router, global_dispatcher
    logger.info("🚀 AI 秘書服務正在啟動（Lifespan 開始）...")
    
    # 在背景嘗試初始化 Google 服務，不要阻塞啟動
    async def initialize_services():
        global llm_service, intent_router, global_dispatcher
        try:
            logger.info("正在初始化 Google 與 AI 服務...")
            # 延遲建立服務實例
            llm_service = LLMService(Config.GEMINI_API_KEY)
            intent_router = IntentRouter(Config.GEMINI_API_KEY)
            
            # 取得 Google 服務 (這通常是最耗時或最容易出錯的地方)
            gmail, calendar, tasks, sheets = get_google_services()
            
            global_dispatcher = ActionDispatcher(
                line_service, 
                llm_service, 
                gmail, 
                calendar, 
                tasks, 
                sheets
            )
            
            # 設定排程器
            scheduler = setup_scheduler(line_service.api, line_service.user_id)
            app.state.scheduler = scheduler
            logger.info("✅ 內部服務（Google/LLM/Scheduler）已就緒。")
        except Exception as e:
            logger.error(f"⚠️ 背景服務初始化出錯 (但不妨礙埠口監聽): {e}")

    # 異步執行初始化
    asyncio.create_task(initialize_services())
    
    logger.info("✨ 伺服器核心已就緒，準備接收 Webhook。")
    yield
    
    logger.info("🛑 正在停止服務...")
    if hasattr(app.state, "scheduler"):
        app.state.scheduler.shutdown()

# 應用程式實例
app = FastAPI(title="AI Secretary System", lifespan=lifespan)

@app.get("/", response_class=HTMLResponse)
async def root():
    status = "🟢 服務正常" if global_dispatcher else "🟡 核心載入中"
    return f"""
    <html>
        <head><title>AI Secretary</title></head>
        <body style="font-family: Arial; text-align: center; padding-top: 50px;">
            <h1>🤖 AI 秘書伺服器 ({status})</h1>
            <p>與您的 LINE Bot 互動來管理所有事務。</p>
        </body>
    </html>
    """

@app.post("/callback")
async def callback(request: Request):
    signature = request.headers.get("X-Line-Signature", "")
    body = await request.body()
    body_str = body.decode("utf-8")

    try:
        line_service.handler.handle(body_str, signature)
    except InvalidSignatureError:
        raise HTTPException(status_code=400, detail="Invalid signature.")
    except Exception as e:
        logger.error(f"Webhook 處理異常: {e}")
        raise HTTPException(status_code=500, detail="Internal server error.")

    return "OK"

@line_service.handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    if not global_dispatcher:
        line_service.reply_text(event.reply_token, "秘書正在醒來的路上，請稍等一分鐘再對我下指令。")
        return

    user_id = event.source.user_id
    user_message = event.message.text.strip()
    
    if user_id != line_service.user_id:
        return

    if user_message == "測試排程":
        asyncio.create_task(send_morning_briefing(line_service.api, user_id))
        line_service.reply_text(event.reply_token, "好的老闆，正在執行簡報測試...")
        return

    analysis_result = intent_router.classify_intent(user_message)
    intent = analysis_result.get("intent", "Chat")
    global_dispatcher.dispatch(intent, user_message, user_id, reply_token=event.reply_token)

if __name__ == "__main__":
    import uvicorn
    # 這裡的 PORT 由 Config 決定 (Cloud Run 會提供 8080)
    uvicorn.run(app, host="0.0.0.0", port=Config.PORT)
