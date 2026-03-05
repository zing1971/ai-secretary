import sys
import os
import unittest
from unittest.mock import MagicMock, patch, PropertyMock

# 加入路徑
sys.path.append(os.getcwd())

# 模擬所有可能導致 import 失敗的外部庫
class MockClient:
    def __init__(self, *args, **kwargs):
        self.models = MagicMock()

# 全面模擬 google 模組
mock_google = MagicMock()
mock_google.genai.Client = MockClient
sys.modules['google'] = mock_google
sys.modules['google.genai'] = mock_google.genai
sys.modules['google.auth'] = MagicMock()
sys.modules['google.auth.transport'] = MagicMock()
sys.modules['google.auth.transport.requests'] = MagicMock()
sys.modules['google.oauth2'] = MagicMock()
sys.modules['google_auth_oauthlib'] = MagicMock()
sys.modules['googleapiclient'] = MagicMock()
sys.modules['googleapiclient.discovery'] = MagicMock()

# 為了避免 intent_router.py 執行時報錯，先把 clean_api_key 處理好
with patch('google_auth.clean_api_key', side_effect=lambda x: x):
    from intent_router import IntentRouter
    from action_dispatcher import ActionDispatcher
    from llm_service import LLMService

class ComprehensiveTest(unittest.TestCase):
    
    @patch('intent_router.genai.Client')
    def test_routing_logic(self, mock_client):
        print("\n--- 測試 1: 意圖路由 ---")
        router = IntentRouter("fake_key")
        
        # 規則匹配：信件
        res = router.classify_intent("找信件")
        print(f"輸入 '找信件' -> 意圖: {res['intent']}")
        self.assertEqual(res['intent'], "Query_Email")
        
        # 歧義偵測：LLM 回傳兩個候選
        mock_response = MagicMock()
        mock_response.text = '{"intent": "Search_Drive", "intent_secondary": ["Query_Advisor"], "ambiguity_reason": "可能有檔案或知識庫"}'
        router.client.models.generate_content.return_value = mock_response
        
        res = router.classify_intent("這份簡報怎麼寫？")
        print(f"輸入 '這份簡報怎麼寫？' (模擬歧義) -> 意圖: {res['intent']}")
        self.assertEqual(res['intent'], "Clarify_Intent")
        self.assertIn("candidates", res)

    @patch('action_dispatcher.NotebookLMService')
    @patch('action_dispatcher.MemoryService')
    def test_dispatcher_clarification(self, mock_mem, mock_nb):
        print("\n--- 測試 2: 澄清機制邏輯 ---")
        mock_line = MagicMock()
        mock_llm = MagicMock()
        # 建立 dispatcher，注意 __init__ 會用到這些 mock
        dispatcher = ActionDispatcher(mock_line, mock_llm, None, None, None, None)
        
        user_id = "user_123"
        dispatcher._pending_clarification[user_id] = {
            "query": "專案",
            "candidates": ["Search_Drive", "Query_Advisor"],
            "timestamp": MagicMock() # 跳過時間檢查
        }
        
        with patch.object(dispatcher, 'dispatch') as mock_dispatch:
            dispatcher._handle_clarification_choice(user_id, "1")
            # 應該重導向到 Search_Drive
            mock_dispatch.assert_called()
            self.assertEqual(mock_dispatch.call_args[1]['intent_override'], "Search_Drive")
            print("澄清選擇 '1' 成功重導向至 Search_Drive")

    @patch('llm_service.genai.Client')
    def test_source_url_injection(self, mock_gen):
        print("\n--- 測試 3: 來源 URL 注入 ---")
        llm = LLMService()
        emails = [{
            "sender": "Alice", "subject": "Test", "body": "Hello", 
            "url": "https://mail.google.com/test"
        }]
        
        # 檢查提示詞中是否包含 URL
        with patch.object(llm.client.models, 'generate_content') as mock_gen_content:
            llm.format_email_summary(emails, "測試")
            instruction = mock_gen_content.call_args[1]['config']['system_instruction']
            self.assertIn("URL", instruction)
            self.assertIn("🔗 查看原信", instruction)
            self.assertIn("https://mail.google.com/test", instruction)
            print("Email 摘要 Prompt 成功注入來源網址引用指示與資料連結")

if __name__ == '__main__':
    unittest.main()
