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
from gmail_service import get_recent_emails

# 載入環境變數
load_dotenv(override=True)

app = FastAPI(title="AI Secretary Line Webhook")

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

# 全局變數暫存服務 (為簡化先在此取得)
gmail_service, calendar_service = None, None
try:
    gmail_service, calendar_service = get_google_services()
except Exception as e:
    print(f"啟動時 Google 驗證失敗: {e}")

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

    # 呼叫意圖分析
    analysis_result = intent_router.analyze_intent(user_message)
    intent = analysis_result.get("intent", "Unknown")
    reply_text = analysis_result.get("reply_message", "抱歉老闆，我無法理解您的指令。")
    
    print(f"判斷意圖為: {intent}")
    
    # 根據意圖執行不同動作
    additional_info = ""
    if intent == "Query_Calendar":
        if calendar_service:
            events = get_todays_events(calendar_service)
            if events:
                additional_info = "\n\n【最新行程資料】\n" + "\n".join(events)
            else:
                additional_info = "\n\n【訊息記錄】\n今天似乎沒有其它已排定的行程。"
        else:
            additional_info = "\n\n(抱歉，行事曆服務目前無法連線)"
            
    elif intent == "Query_Email":
        if gmail_service:
            emails = get_recent_emails(gmail_service)
            if emails:
                additional_info = "\n\n【信件清單】\n" + "\n".join(emails[:5]) # 避免超過字數限制，先取前五封
            else:
                additional_info = "\n\n【訊息記錄】\n過去 24 小時內沒有偵測到未讀信件。"
        else:
            additional_info = "\n\n(抱歉，信箱服務目前無法連線)"
    
    # 將 AI 回覆和撈取到的資料組合
    final_reply = reply_text + additional_info
    
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=final_reply)
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
