import os
import sys
import logging
from dotenv import load_dotenv
from google_auth import clean_api_key

# 載入環境變數
load_dotenv(override=True)

# 設定 Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("AI-Secretary")

class Config:
    @staticmethod
    def _get_env(key, default=None):
        # 雲端環境中可能不小心在變數名尾端多加了空白，這裡進行徹底比對
        val = os.getenv(key)
        if val is None:
            # 嘗試搜尋是否有帶空白的同名變數
            for k, v in os.environ.items():
                if k.strip() == key:
                    return v
        return val if val is not None else default

    LINE_CHANNEL_ACCESS_TOKEN = _get_env.__func__("LINE_CHANNEL_ACCESS_TOKEN")
    LINE_CHANNEL_SECRET = _get_env.__func__("LINE_CHANNEL_SECRET")
    LINE_USER_ID = _get_env.__func__("LINE_USER_ID")
    GEMINI_API_KEY = clean_api_key(_get_env.__func__("GEMINI_API_KEY", ""))
    GOOGLE_SHEET_ID = _get_env.__func__("GOOGLE_SHEET_ID")
    
    PORT = int(os.getenv("PORT", 8080))
    DEBUG = os.getenv("DEBUG", "False").lower() in ("true", "1", "t")

    @classmethod
    def validate(cls):
        # 雲端環境中，若部署才剛開始，可能變數尚未設定，這裡加入偵測
        is_cloud = os.environ.get("DEPLOY_ENV") == "cloud"
        missing = []
        if not cls.LINE_CHANNEL_ACCESS_TOKEN: missing.append("LINE_CHANNEL_ACCESS_TOKEN")
        if not cls.LINE_CHANNEL_SECRET: missing.append("LINE_CHANNEL_SECRET")
        if not cls.LINE_USER_ID: missing.append("LINE_USER_ID")
        if not cls.GEMINI_API_KEY: missing.append("GEMINI_API_KEY")
        if not cls.GOOGLE_SHEET_ID: missing.append("GOOGLE_SHEET_ID")
        
        if missing:
            msg = f"缺少必要的環境變數: {', '.join(missing)}"
            if is_cloud:
                logger.error(f"❌ [雲端部署錯誤]: {msg}。請在 Cloud Run 控制台設定環境變數。")
            else:
                logger.error(f"❌ [本地錯誤]: {msg}")
            sys.exit(1)
        
        logger.info("環境變數驗證通過。")

# 立即執行驗證
Config.validate()
