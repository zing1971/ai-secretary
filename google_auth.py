import os.path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# 如果修改這些 SCOPES，請刪除 token.json。
SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.compose',
    'https://www.googleapis.com/auth/calendar.readonly',
    'https://www.googleapis.com/auth/tasks'
]

def get_google_services():
    """取得 Gmail、Calendar 與 Tasks API 服務。"""
    creds = None
    # token.json 儲存使用者的存取與重新整理權杖。
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    
    # 如果沒有有效的憑證，讓使用者登入。
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists('credentials.json'):
                raise FileNotFoundError("請確保 credentials.json 檔案存在於專案根目錄。")
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            # 固定 port 8080，避免隨機 port 導致部分環境授權失敗
            creds = flow.run_local_server(port=8080)
        
        # 儲存下一次執行使用的憑證
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    gmail_service = build('gmail', 'v1', credentials=creds)
    calendar_service = build('calendar', 'v3', credentials=creds)
    tasks_service = build('tasks', 'v1', credentials=creds)
    
    return gmail_service, calendar_service, tasks_service
