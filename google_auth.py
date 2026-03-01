import os.path
import json
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# 如果修改這些 SCOPES，請刪除 token.json。
SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.compose',
    'https://www.googleapis.com/auth/calendar.readonly',
    'https://www.googleapis.com/auth/tasks',
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]

def clean_api_key(api_key: str) -> str:
    """清理 API KEY (處理引號與重複貼上問題)。"""
    if not api_key:
        return ""
    api_key = api_key.strip().replace('"', '').replace("'", "")
    if len(api_key) == 78:
        api_key = api_key[:39]
    return api_key

def get_google_services():
    """取得 Gmail、Calendar、Tasks、Sheets、Drive API 服務。"""
    creds = None
    
    # 支援從環境變數讀取 token (Cloud Run 必備)
    token_env = os.getenv("GOOGLE_TOKEN_JSON")
    if token_env:
        try:
            token_data = json.loads(token_env)
            creds = Credentials.from_authorized_user_info(token_data, SCOPES)
        except Exception as e:
            print(f"從環境變數讀取 Token 失敗: {e}")

    # 若環境變數沒有，則讀取本地檔案
    if not creds and os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    
    # 如果沒有有效的憑證，讓使用者登入或重新整理
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            # 支援從環境變數讀取 credentials (Cloud Run 必備)
            creds_env = os.getenv("GOOGLE_CREDENTIALS_JSON")
            if creds_env:
                try:
                    creds_data = json.loads(creds_env)
                    flow = InstalledAppFlow.from_client_config(creds_data, SCOPES)
                    # 雲端環境無法彈出視窗，通常需依賴事先生成的 token.json
                    # 這裡保留 logic 防止本地遺失時可觸發流程
                    if not os.environ.get("DEPLOY_ENV") == "cloud":
                        creds = flow.run_local_server(port=8080)
                except Exception as e:
                    print(f"從環境變數讀取 Credentials 失敗: {e}")

            if not creds:
                if not os.path.exists('credentials.json'):
                    raise FileNotFoundError("請確保 credentials.json 檔案存在或已設定 GOOGLE_CREDENTIALS_JSON 環境變數。")
                flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
                creds = flow.run_local_server(port=8080)
        
        # 儲存下一次執行使用的憑證 (如果在開發環境下)
        if not os.environ.get("DEPLOY_ENV") == "cloud":
            with open('token.json', 'w') as token:
                token.write(creds.to_json())

    gmail_service = build('gmail', 'v1', credentials=creds)
    calendar_service = build('calendar', 'v3', credentials=creds)
    tasks_service = build('tasks', 'v1', credentials=creds)
    sheets_service = build('sheets', 'v4', credentials=creds)
    drive_service = build('drive', 'v3', credentials=creds)
    
    return gmail_service, calendar_service, tasks_service, sheets_service, drive_service
