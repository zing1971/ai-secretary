import os
import sys
import logging
from dotenv import load_dotenv

# 載入環境變數
load_dotenv(override=True)

# 設定 Logging
import io
if sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
if sys.stderr.encoding.lower() != 'utf-8':
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

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
    return api_key.strip().replace('"', '').replace("'", "")


class Config:
    # ── Telegram ─────────────────────────────────────────────────
    TELEGRAM_BOT_TOKEN = _get_env("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHAT_ID   = _get_env("TELEGRAM_CHAT_ID", "")

    # ── 系統環境 ─────────────────────────────────────────────────
    PORT = int(os.getenv("PORT", "8080"))
    DEBUG = os.getenv("DEBUG", "False").lower() in ("true", "1", "t")

    GEMINI_API_KEY = _clean_api_key(_get_env("GEMINI_API_KEY", ""))
    GOOGLE_SHEET_ID = _get_env("GOOGLE_SHEET_ID", "")

    NOTEBOOK_ID_INFOSEC = _get_env("NOTEBOOK_ID_INFOSEC", "")
    NOTEBOOK_ID_IT = _get_env("NOTEBOOK_ID_IT", "")
    NOTEBOOK_ID_TRENDS = _get_env("NOTEBOOK_ID_TRENDS", "")

    @classmethod
    def validate(cls):
        """驗證環境變數，但絕不在 import 時呼叫 sys.exit"""
        missing = []
        if not cls.TELEGRAM_BOT_TOKEN:
            missing.append("TELEGRAM_BOT_TOKEN")
        if not cls.GEMINI_API_KEY:
            missing.append("GEMINI_API_KEY")
        if not cls.GOOGLE_SHEET_ID:
            missing.append("GOOGLE_SHEET_ID")

        if missing:
            logger.error(f"❌ 缺少必要環境變數: {', '.join(missing)}")
            return False

        if not cls.TELEGRAM_CHAT_ID:
            logger.warning("⚠️ 缺少 TELEGRAM_CHAT_ID，目前處於「未配對模式」。請傳送訊息給機器人並在日誌中查看您的 Chat ID。")
        else:
            logger.info("✅ 環境變數驗證通過。")
            
        return True


# ⚠️ 注意：此處 **絕不** 呼叫 sys.exit
# 驗證留給 app.py 的 lifespan 去做
logger.info(f"Config 載入完成：PORT={Config.PORT}, SHEET_ID={'已設定' if Config.GOOGLE_SHEET_ID else '未設定'}")
