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


def _get_env(key, default=None):
    """強健地獲取環境變數，自動處理 key 名稱尾端空白與值的引號"""
    val = os.getenv(key)
    if val is None:
        for k, v in os.environ.items():
            if k.strip() == key:
                val = v
                break
    if val is None:
        return default
    if isinstance(val, str):
        val = val.strip().replace('"', '').replace("'", "")
    return val


def _clean_api_key(api_key: str) -> str:
    if not api_key:
        return ""
    api_key = api_key.strip().replace('"', '').replace("'", "")
    if len(api_key) == 78:
        api_key = api_key[:39]
    return api_key


class Config:
    LINE_CHANNEL_ACCESS_TOKEN = _get_env("LINE_CHANNEL_ACCESS_TOKEN", "")
    LINE_CHANNEL_SECRET = _get_env("LINE_CHANNEL_SECRET", "")
    LINE_USER_ID = _get_env("LINE_USER_ID", "")
    GEMINI_API_KEY = _clean_api_key(_get_env("GEMINI_API_KEY", ""))
    GOOGLE_SHEET_ID = _get_env("GOOGLE_SHEET_ID", "")
    PINECONE_API_KEY = _get_env("PINECONE_API_KEY", "")

    PORT = int(os.getenv("PORT", "8080"))
    DEBUG = os.getenv("DEBUG", "False").lower() in ("true", "1", "t")

    @classmethod
    def validate(cls):
        """驗證環境變數，但絕不在 import 時呼叫 sys.exit"""
        missing = []
        if not cls.LINE_CHANNEL_ACCESS_TOKEN:
            missing.append("LINE_CHANNEL_ACCESS_TOKEN")
        if not cls.LINE_CHANNEL_SECRET:
            missing.append("LINE_CHANNEL_SECRET")
        if not cls.LINE_USER_ID:
            missing.append("LINE_USER_ID")
        if not cls.GEMINI_API_KEY:
            missing.append("GEMINI_API_KEY")
        if not cls.GOOGLE_SHEET_ID:
            missing.append("GOOGLE_SHEET_ID")

        if missing:
            logger.error(f"❌ 缺少環境變數: {', '.join(missing)}")
            return False

        if not cls.PINECONE_API_KEY:
            logger.warning("⚠️ 未設定 PINECONE_API_KEY，Pinecone 向量記憶功能將停用")

        logger.info("✅ 環境變數驗證通過。")
        return True


# ⚠️ 注意：此處 **絕不** 呼叫 sys.exit
# 驗證留給 app.py 的 lifespan 去做
logger.info(f"Config 載入完成：PORT={Config.PORT}, SHEET_ID={'已設定' if Config.GOOGLE_SHEET_ID else '未設定'}")
