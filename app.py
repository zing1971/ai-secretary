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

# 初始化全句服務實例 (由 lifespan 管理生命週期)
line_service = LineService()
llm_service = LLMService(Config.GEMINI_API_KEY)
intent_router = IntentRouter(Config.GEMINI_API_KEY)
global_dispatcher = None

# 1. FastAPI Lifespan 管理
@asynccontextmanager
async def lifespan(app: FastAPI):
    global global_dispatcher
    logger.info("正在啟動 AI 秘書服務...")
    
    try:
        # 取得 Google 服務
        gmail, calendar, tasks, sheets = get_google_services()
        
        # 初始化全域分流器
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
        logger.info("✅ 背景服務與排程器已就緒。")
    except Exception as e:
        logger.error(f"❌ 啟動失敗: {e}")
        raise e

    yield
    
    logger.info("正在停止 AI 秘書服務...")
    if hasattr(app.state, "scheduler"):
        app.state.scheduler.shutdown()

# 2. 初始化應用
app = FastAPI(title="AI Secretary System", lifespan=lifespan)

# 3. Web 介面入口
@app.get("/", response_class=HTMLResponse)
async def root():
    return """
    <html>
        <head><title>AI Secretary</title></head>
        <body style="font-family: Arial; text-align: center; padding-top: 50px;">
            <h1>🤖 AI 秘書伺服器正在運行中</h1>
            <p>與您的 LINE Bot 互動來管理所有事務。</p>
        </body>
    </html>
    """

# 4. LINE Webhook Handler
@app.post("/callback")
async def callback(request: Request):
    signature = request.headers.get("X-Line-Signature", "")
    body = await request.body()
    body_str = body.decode("utf-8")

    try:
        line_service.handler.handle(body_str, signature)
    except InvalidSignatureError:
        logger.warning("身分驗證簽名錯誤，請檢查 Secret 金鑰。")
        raise HTTPException(status_code=400, detail="Invalid signature.")
    except Exception as e:
        logger.error(f"Webhook 處理異常: {e}")
        raise HTTPException(status_code=500, detail="Internal server error.")

    return "OK"

# 5. LINE 訊息處理邏輯
@line_service.handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    user_message = event.message.text.strip()
    
    logger.info(f"收到來自 {user_id} 的訊息: {user_message}")

    # A. 權限控管
    if user_id != line_service.user_id:
        logger.warning(f"偵測到非授權使用者 ({user_id})，拒絕服務。")
        return

    # B. 手動指令：測試排程推送
    if user_message == "測試排程":
        asyncio.create_task(send_morning_briefing(line_service.api, user_id))
        line_service.reply_text(event.reply_token, "好的老闆，正在為您即時模擬『早安簡報』推送程序，請稍候...")
        return

    # C. 常規流程：意圖分析
    analysis_result = intent_router.classify_intent(user_message)
    intent = analysis_result.get("intent", "Chat")
    
    logger.info(f"AI 識別意圖：{intent}")

    # D. 根據意圖調派業務邏輯
    if global_dispatcher:
        # 傳遞 reply_token 以利回覆
        global_dispatcher.dispatch(intent, user_message, user_id, reply_token=event.reply_token)
    else:
        line_service.reply_text(event.reply_token, "系統初始化中，請稍後再試。")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=Config.PORT)
