import logging
import os
import os.path
import sys
import json
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)

# 以 google_auth.py 所在目錄為基準，確保不受 CWD 影響
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_TOKEN_PATH = os.path.join(_BASE_DIR, "token.json")
_CREDS_PATH = os.path.join(_BASE_DIR, "credentials.json")

# 如果修改這些 SCOPES，請刪除 token.json。
SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.compose',
    'https://www.googleapis.com/auth/calendar',
    'https://www.googleapis.com/auth/tasks',
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/contacts'
]

# 判斷是否為無顯示器的非互動環境（VPS / systemd / subprocess pipe）
# 兩個條件都要成立才算 headless：stdin 不是 tty 且沒有可用的顯示器/終端
_is_headless = (
    not sys.stdin.isatty()
    and not os.environ.get(
        "DISPLAY",
        os.environ.get(
            "WAYLAND_DISPLAY",
            os.environ.get("TERM_PROGRAM", "")
        )
    )
)


def clean_api_key(api_key: str) -> str:
    """清理 API KEY (處理引號與空格問題)。"""
    if not api_key:
        return ""
    # 只去除首尾空格、換行與引號
    return api_key.strip().replace('"', '').replace("'", "")


def get_credentials():
    """取得 Google OAuth2 憑證 (Credentials) 物件。"""
    creds = None

    # 支援從環境變數讀取 token (Cloud Run 必備)
    token_env = os.getenv("GOOGLE_TOKEN_JSON")
    if token_env:
        try:
            token_data = json.loads(token_env)
            creds = Credentials.from_authorized_user_info(token_data, SCOPES)
        except Exception as e:
            logger.warning(f"從環境變數讀取 Token 失敗: {e}")

    # 若環境變數沒有，則讀取本地檔案
    if not creds and os.path.exists(_TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(_TOKEN_PATH, SCOPES)

    # 如果沒有有效的憑證，讓使用者登入或重新整理
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                if _is_headless:
                    raise RuntimeError(
                        f"Google Token 刷新失敗（{e}）。\n"
                        "請在本機重新執行 OAuth 授權並上傳新的 token.json：\n"
                        "  1. 本機執行：python -c \"from google_auth import get_credentials; get_credentials()\"\n"
                        "  2. 上傳：gcloud compute scp credentials.json token.json <user>@<instance>:/home/<user>/ai-secretary/ --zone=<zone>\n"
                        "  3. VPS 重啟：sudo systemctl restart ai-secretary"
                    ) from e
                logger.warning(f"Token 刷新失敗: {e}，將重新執行授權流程")
                creds = None  # 強制重新登入流程（僅本機互動環境）

        if not creds:
            if _is_headless:
                raise RuntimeError(
                    "Google OAuth 憑證無效且無法在非互動環境下重新授權。\n"
                    "請在本機重新執行 OAuth 授權並上傳新的 token.json：\n"
                    "  1. 本機執行：python -c \"from google_auth import get_credentials; get_credentials()\"\n"
                    "  2. 上傳：gcloud compute scp credentials.json token.json <user>@<instance>:/home/<user>/ai-secretary/ --zone=<zone>\n"
                    "  3. VPS 重啟：sudo systemctl restart ai-secretary"
                )

            # 支援從環境變數讀取 credentials (Cloud Run 必備)
            creds_env = os.getenv("GOOGLE_CREDENTIALS_JSON")
            if creds_env:
                try:
                    creds_data = json.loads(creds_env)
                    flow = InstalledAppFlow.from_client_config(creds_data, SCOPES)
                    creds = flow.run_local_server(port=8080)
                except Exception as e:
                    logger.error(f"從環境變數讀取 Credentials 失敗: {e}")

            if not creds:
                if not os.path.exists(_CREDS_PATH):
                    raise FileNotFoundError(
                        "請確保 credentials.json 檔案存在或已設定 GOOGLE_CREDENTIALS_JSON 環境變數。"
                    )
                flow = InstalledAppFlow.from_client_secrets_file(_CREDS_PATH, SCOPES)
                creds = flow.run_local_server(
                    port=8080,
                    access_type='offline',
                    prompt='consent'
                )

        # 儲存 token 供下次使用（本機開發環境：DEPLOY_ENV 未設定或為非 cloud 值）
        deploy_env = os.environ.get("DEPLOY_ENV", "").lower()
        if creds and deploy_env not in ("cloud", "production"):
            try:
                with open(_TOKEN_PATH, 'w') as token:
                    token.write(creds.to_json())
            except OSError as e:
                logger.warning(f"無法寫入 token.json: {e}")

    return creds


def get_google_services():
    """取得 Gmail、Calendar、Tasks、Sheets、Drive、People API 服務。"""
    creds = get_credentials()
    if not creds:
        return None, None, None, None, None, None

    gmail_service = build('gmail', 'v1', credentials=creds)
    calendar_service = build('calendar', 'v3', credentials=creds)
    tasks_service = build('tasks', 'v1', credentials=creds)
    sheets_service = build('sheets', 'v4', credentials=creds)
    drive_service = build('drive', 'v3', credentials=creds)
    people_service = build('people', 'v1', credentials=creds)

    return gmail_service, calendar_service, tasks_service, sheets_service, drive_service, people_service
