import sys
import os
import unittest
from unittest.mock import MagicMock, patch

# 加入路徑
sys.path.append(os.getcwd())

# 模擬環境變數與外部庫
os.environ["GEMINI_API_KEY"] = "fake_key"
os.environ["TELEGRAM_BOT_TOKEN"] = "fake_token"
os.environ["TELEGRAM_CHAT_ID"] = "123456"
os.environ["GOOGLE_SHEET_ID"] = "fake_sheet"

# 徹底模擬 google 模組套件
for m in [
    'google', 'google.genai', 'google.auth', 'google.auth.transport', 
    'google.auth.transport.requests', 'google.oauth2', 'google.oauth2.credentials', 
    'google_auth_oauthlib', 'google_auth_oauthlib.flow', 
    'googleapiclient', 'googleapiclient.discovery'
]:
    sys.modules[m] = MagicMock()

from role_dispatcher import RoleDispatcher
from telegram_service import TelegramService
from llm_service import LLMService
from intent_router import IntentRouter

class MenuNavigationTest(unittest.TestCase):
    
    def setUp(self):
        # 1. 模擬 TelegramService
        self.mock_tg = MagicMock(spec=TelegramService)
        self.mock_tg.chat_id = "123456"
        
        # 2. 模擬 LLMService
        self.mock_llm = MagicMock(spec=LLMService)
        
        # 3. 建立 Dispatcher
        # 模擬所需的 Google 服務對象
        self.dispatcher = RoleDispatcher(
            self.mock_tg, self.mock_llm,
            gmail=MagicMock(), calendar=MagicMock(), tasks=MagicMock(), sheets=MagicMock()
        )
        
        # 4. 模擬 IntentRouter
        self.router = IntentRouter("fake_key")

    def test_email_menu_trigger(self):
        print("\n--- 測試 B-1: 郵件處理中心導引 ---")
        user_msg = "進入郵件處理中心"
        
        # 模擬 IntentRouter 回傳意圖
        intent_data = {"intent": "Query_Email", "search_keyword": ""}
        
        # 執行分流
        self.dispatcher.dispatch(intent_data, user_msg, "123456", "123456")
        
        # 驗證是否呼叫了 send_email_menu
        self.mock_tg.send_email_menu.assert_called_once_with("123456")
        print("✅ 成功觸發郵件中心子選單")

    def test_knowledge_menu_trigger(self):
        print("\n--- 測試 C-1: 專業知識庫導引 ---")
        user_msg = "開啟專業知識庫"
        
        # 模擬 IntentRouter 回傳意圖
        intent_data = {"intent": "Query_Project_Advisor", "domain": "it"}
        
        # 執行分流
        self.dispatcher.dispatch(intent_data, user_msg, "123456", "123456")
        
        # 驗證是否呼叫了 send_knowledge_menu
        self.mock_tg.send_knowledge_menu.assert_called_once_with("123456")
        print("✅ 成功觸發知識搜尋子選單")

    def test_settings_menu_trigger(self):
        print("\n--- 測試 D-1: 系統設定與偏好導引 ---")
        user_msg = "查看個人偏好與設定"
        
        # 模擬 IntentRouter 回傳意圖
        intent_data = {"intent": "Memory_Update"}
        
        # 模擬 MemoryService 的回傳
        self.dispatcher.memory.fetch_relevant_memories = MagicMock(return_value="仁哥喜歡喝黑咖啡，不加糖。")
        
        # 執行分流
        self.dispatcher.dispatch(intent_data, user_msg, "123456", "123456")
        
        # 驗證是否呼叫了 send_settings_menu 並帶入記憶內容
        self.mock_tg.send_settings_menu.assert_called_once()
        args, kwargs = self.mock_tg.send_settings_menu.call_args
        self.assertIn("黑咖啡", args[0])
        print("✅ 成功觸發系統設定選單並讀取個人偏好")

    def test_briefing_regression(self):
        print("\n--- 測試 A-1: 每日簡報功能回歸 ---")
        # 模擬 handle_proactive_process 會呼叫 birdie
        self.dispatcher.birdie.handle_proactive_process = MagicMock(return_value="今日有一封重要信件。")
        
        report = self.dispatcher.handle_proactive_process()
        self.assertEqual(report, "今日有一封重要信件。")
        print("✅ 每日簡報邏輯回歸正常")

if __name__ == '__main__':
    unittest.main()
