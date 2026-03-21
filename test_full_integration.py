import os
import json
import logging
from dotenv import load_dotenv
from intent_router import IntentRouter
from role_dispatcher import RoleDispatcher
from llm_service import LLMService
from google_auth import get_google_services
from config import Config

# 強制重新載入環境變數
load_dotenv(override=True)

# 設置模擬 UserID
TEST_USER_ID = "test_chat_id"

class MockMessagingService:
    def __init__(self):
        self.messages = []
        self.chat_id = "test_chat_id"
    
    def reply_text(self, reply_token, text):
        self.messages.append(f"[Reply] {text}")
        return True
    
    def push_text(self, text, to_user_id=None):
        self.messages.append(f"[Push] {text}")
        return True

def test_full_flow():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY not found")
        return

    # 初始化服務
    msg_mock = MockMessagingService()
    llm = LLMService(api_key=api_key)
    
    print("正在取得 Google 服務權限...")
    try:
        gmail, cal, tasks, sheets, drive, people = get_google_services()
    except Exception as e:
        print(f"Google 授權失敗: {e}")
        return

    # 使用 RoleDispatcher 取代舊的 ActionDispatcher
    dispatcher = RoleDispatcher(msg_mock, llm, gmail, cal, tasks, sheets, drive, people)
    router = IntentRouter(api_key=api_key)

    test_cases = [
        {"tag": "A1", "msg": "查詢我未來2天的行程安排，提醒需要準備的事項"},
        {"tag": "A2", "msg": "摘要最新15封郵件重點，標註需要回覆的信"},
        {"tag": "B1", "msg": "今日簡報"},
    ]

    print(f"\n{'Tag':<5} | {'Message':<50} | {'Status'}")
    print("-" * 80)

    for case in test_cases:
        msg = case["msg"]
        tag = case["tag"]
        msg_mock.messages = [] # 清空
        
        print(f"測試請求 [{tag}]: {msg}")
        
        try:
            # 1. 意圖識別
            intent_data = router.classify_intent(msg)
            intent = intent_data.get("intent")
            print(f"识别意圖: {intent}")
            
            # 2. 執行分派 (模擬 Webhook 進入 dispatch)
            dispatcher.dispatch(intent_data, msg, TEST_USER_ID, reply_token="dummy_token")
            
            # 3. 檢查回覆數量與內容
            msg_count = len(msg_mock.messages)
            print(f"收到回覆數: {msg_count}")
            for m in msg_mock.messages:
                # 只印出前 50 個字，避免洗版
                content = m.replace('\n', ' ')
                print(f"  -> {content[:100]}...")
            
            if msg_count >= 1:
                print(f"✅ [{tag}] 通過: 偵測到回覆流程")
            else:
                print(f"❌ [{tag}] 失敗: 未收到任何回覆")
            
        except Exception as e:
            print(f"❌ [{tag}] 執行出錯: {e}")
        print("-" * 80)

if __name__ == "__main__":
    test_full_flow()
