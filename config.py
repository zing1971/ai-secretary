import os
import sys
import logging
from dotenv import load_dotenv

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

def clean_api_key(api_key: str) -> str:
    """清理 API KEY (處理引號與重複貼上問題)。"""
    if not api_key:
        return ""
    api_key = api_key.strip().replace('"', '').replace("'", "")
    if len(api_key) == 78:
        api_key = api_key[:39]
    return api_key

def get_env_robust(key, default=None):
    """強健地獲取環境變數，自動處理尾端空白與引號"""
    # 1. 直接獲取
    val = os.getenv(key)
    
    # 2. 如果找不到，嘗試掃描所有 key (處理名稱帶空白的情況)
    if val is None:
        for k, v in os.environ.items():
            if k.strip() == key:
                val = v
                break
    
    # 3. 如果還是找不到，返回預設值
    if val is None:
        return default
    
    # 4. 清理值的內容 (去除引號與空白)
    if isinstance(val, str):
        val = val.strip().replace('"', '').replace("'", "")
        
    return val

class Config:
    LINE_CHANNEL_ACCESS_TOKEN = get_env_robust("LINE_CHANNEL_ACCESS_TOKEN")
    LINE_CHANNEL_SECRET = get_env_robust("LINE_CHANNEL_SECRET")
    LINE_USER_ID = get_env_robust("LINE_USER_ID")
    GEMINI_API_KEY = clean_api_key(get_env_robust("GEMINI_API_KEY", ""))
    GOOGLE_SHEET_ID = get_env_robust("GOOGLE_SHEET_ID")
    
    PORT = int(os.getenv("PORT", 8080))
    DEBUG = os.getenv("DEBUG", "False").lower() in ("true", "1", "t")

    @classmethod
    def validate(cls):
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
                logger.error(f"❌ [雲端部署錯誤]: {msg}。")
                # 雲端環境若缺少變數時建議先不要 sys.exit，讓啟動能繼續以便觀察更多 Log
                # 但 Cloud Run 需要 8080 埠口回應，這裡我們拋出異常
                raise ValueError(msg)
            else:
                logger.error(f"❌ [本地錯誤]: {msg}")
                sys.exit(1)
        
        logger.info("✅ 環境變數驗證通過。")

# 立即執行驗證
try:
    Config.validate()
except Exception as e:
    logger.error(f"啟動前驗證失敗，請檢查 GCP 控制台設定: {e}")
    # 仍然需要退出以防止無效運行
    sys.exit(1)
