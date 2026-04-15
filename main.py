"""
AI Secretary (Hermes Agent 架構) - 入口點

啟動順序：
1. 驗證環境變數
2. 同步 persona_soul.md → ~/.hermes/SOUL.md
3. 刪除 Telegram webhook（確保 hermes 可使用 polling 模式）
4. 啟動 hermes gateway run（阻塞，polling 模式）
"""
import os
import sys
import shutil
import subprocess
import logging
import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("AI-Secretary")


def sync_persona() -> None:
    """複製 persona_soul.md 至 ~/.hermes/SOUL.md。"""
    hermes_dir = os.path.expanduser("~/.hermes")
    os.makedirs(hermes_dir, exist_ok=True)
    src = os.path.join(os.path.dirname(__file__), "persona_soul.md")
    dst = os.path.join(hermes_dir, "SOUL.md")
    if os.path.exists(src):
        shutil.copy2(src, dst)
        logger.info(f"Persona 已同步至 {dst}")


def delete_webhook(bot_token: str) -> None:
    """刪除 Telegram webhook，確保 hermes 可使用 polling 模式運作。"""
    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{bot_token}/deleteWebhook",
            timeout=10,
        )
        result = resp.json()
        if result.get("ok"):
            logger.info("🗑️  Telegram webhook 已清除，hermes 將使用 polling 模式")
        else:
            logger.warning(f"⚠️  deleteWebhook 失敗：{result.get('description')}")
    except Exception as e:
        logger.warning(f"⚠️  deleteWebhook 例外：{e}")


def main() -> None:
    from config import Config

    if not Config.validate():
        logger.error("環境變數驗證失敗，無法啟動。")
        sys.exit(1)

    sync_persona()
    delete_webhook(Config.TELEGRAM_BOT_TOKEN)

    logger.info("🤖 啟動 Hermes Gateway（polling 模式）...")
    try:
        subprocess.run(["hermes", "gateway", "run"], check=True)
    except FileNotFoundError:
        logger.error("找不到 hermes 指令，請確認已安裝 hermes-agent 套件。")
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("收到中斷訊號，正在關閉...")


if __name__ == "__main__":
    main()
