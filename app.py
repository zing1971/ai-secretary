import os
import sys
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
from dotenv import load_dotenv
from intent_router import IntentRouter
from google_auth import get_google_services
from calendar_service import get_todays_events
from gmail_service import get_recent_emails, create_gmail_draft
from tasks_service import create_google_task
from llm_service import analyze_for_actions
from scheduler_service import setup_scheduler
from contextlib import asynccontextmanager

# 載入環境變數
load_dotenv(override=True)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 啟動時執行：啟動排程器
    scheduler = setup_scheduler(line_bot_api, my_user_id)
    yield
    # 關閉時執行：停止排程器
    scheduler.shutdown()

app = FastAPI(title="AI Secretary Line Webhook", lifespan=lifespan)

line_token = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
line_secret = os.getenv("LINE_CHANNEL_SECRET")
my_user_id = os.getenv("LINE_USER_ID")

if not line_token or not line_secret or not my_user_id:
    print("請確保 .env 檔案中已設定 LINE_CHANNEL_ACCESS_TOKEN, LINE_CHANNEL_SECRET 與 LINE_USER_ID")
    sys.exit(1)

line_bot_api = LineBotApi(line_token)
handler = WebhookHandler(line_secret)

# 初始化意圖路由器
intent_router = IntentRouter()

def get_services():
    """取得 Google 各項服務實例。"""
    try:
        return get_google_services()
    except Exception as e:
        print(f"取得 Google 服務失敗: {e}")
        return None, None, None

@app.get("/", response_class=HTMLResponse)
async def root():
    return "<h1>AI Secretary Webhook is running!</h1>"

@app.post("/callback")
async def callback(request: Request):
    # 取得 X-Line-Signature 標頭值
    signature = request.headers.get("X-Line-Signature", "")

    # 取得請求內容
    body = await request.body()
    body_str = body.decode("utf-8")

    # 處理 webhook 內容
    try:
        handler.handle(body_str, signature)
    except InvalidSignatureError:
        print("Invalid signature. Please check your channel access token/channel secret.")
        raise HTTPException(status_code=400, detail="Invalid signature.")

    return "OK"

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    user_message = event.message.text
    
    print(f"收到來自 {user_id} 的訊息: {user_message}")

    # 權限控管：只處理主人的訊息
    if user_id != my_user_id:
        print(f"非授權使用者 ({user_id}) 嘗試操作，已忽略。")
        return

    # 取得 Google 服務
    gmail_service, calendar_service, tasks_service = get_services()

    # 隱藏指令：手動測試排程推送
    if user_message.strip() == "測試排程":
        from scheduler_service import send_morning_briefing
        import asyncio
        # 使用背景任務執行，避免阻塞 LINE Webhook
        asyncio.create_task(send_morning_briefing(line_bot_api, user_id))
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="好的老闆，正在為您即時模擬『早安簡報』推送程序，請稍候...")
        )
        return

    # 呼叫意圖分析
    analysis_result = intent_router.analyze_intent(user_message)
    intent = analysis_result.get("intent", "Unknown")
    reply_text = analysis_result.get("reply_message", "抱歉老闆，我無法理解您的指令。")
    
    print(f"判斷意圖為: {intent}")
    
    additional_info = ""
    # 根據意圖執行不同動作
    if intent == "Query_Calendar":
        if calendar_service:
            try:
                events = get_todays_events(calendar_service)
                if events:
                    additional_info = "\n\n【最新行程資料】\n" + "\n".join(events)
                else:
                    additional_info = "\n\n【訊息記錄】\n今天似乎沒有其它已排定的行程。"
            except Exception as e:
                additional_info = f"\n\n(行事曆讀取失敗: {e})"
        else:
            additional_info = "\n\n(抱歉，行事曆服務目前無法連線)"
            
    elif intent == "Query_Email":
        if gmail_service:
            try:
                emails = get_recent_emails(gmail_service)
                if emails:
                    summaries = [e['summary_text'] for e in emails[:5]]
                    additional_info = "\n\n【信件清單】\n" + "\n".join(summaries)
                else:
                    additional_info = "\n\n【訊息記錄】\n過去 24 小時內沒有偵測到未讀信件。"
            except Exception as e:
                additional_info = f"\n\n(信件讀取失敗: {e})"
        else:
            additional_info = "\n\n(抱歉，信箱服務目前無法連線)"

    elif intent == "Proactive_Process":
        if not gmail_service or not calendar_service or not tasks_service:
            additional_info = "\n\n抱歉老闆，Google 服務授權不全或連線失敗，無法處理主動任務。"
        else:
            # 取得原始資料
            try:
                events = get_todays_events(calendar_service)
                emails = get_recent_emails(gmail_service)
                
                # 進行 AI 主動分析
                action_data = analyze_for_actions(events, emails)
                
                # 執行動作 1: 建立 Google Tasks 任務
                tasks_created = 0
                for task in action_data.get('tasks', []):
                    create_google_task(tasks_service, task.get('title'), task.get('notes'), task.get('due'))
                    tasks_created += 1
                
                # 執行動作 2: 建立 Gmail 回覆草稿
                drafts_created = 0
                for draft in action_data.get('drafts', []):
                    create_gmail_draft(gmail_service, draft.get('to'), draft.get('subject'), draft.get('body'), draft.get('threadId'))
                    drafts_created += 1
                
                # 組合結果回應
                briefing = action_data.get('briefing', '已為您處理完畢。')
                additional_info = f"\n\n【秘書處理報告】\n{briefing}\n\n已成功為您新增 {tasks_created} 項任務，並擬定 {drafts_created} 封信件草稿。"
            except Exception as e:
                additional_info = f"\n\n主動處理時發生錯誤：{str(e)}"
    
    # 將 AI 回覆和撈取到的資料組合
    final_reply = reply_text + additional_info
    
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=final_reply)
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
