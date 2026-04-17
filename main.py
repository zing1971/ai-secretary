"""
AI Secretary (Hermes Agent 架構) - 入口點

啟動順序：
1. 驗證環境變數
2. 同步 persona_soul.md → ~/.hermes/SOUL.md
3. 注入長期記憶至 SOUL.md 尾部（跨 session 記憶）
4. 刪除 Telegram webhook（確保 hermes 可使用 polling 模式）
5. 啟動 hermes gateway run（阻塞，polling 模式）
"""
import json
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


def inject_memory_to_soul() -> None:
    """
    載入 ~/.hermes/alice_memory.json 並將記憶條目附加至 SOUL.md 尾部。
    讓 hermes 在本 session 啟動時即擁有跨 session 的長期記憶脈絡。
    """
    memory_path = os.path.expanduser("~/.hermes/alice_memory.json")
    soul_path = os.path.expanduser("~/.hermes/SOUL.md")

    if not os.path.exists(memory_path) or not os.path.exists(soul_path):
        return

    try:
        with open(memory_path, "r", encoding="utf-8") as f:
            memory: dict = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.warning(f"⚠️  讀取長期記憶失敗，跳過注入：{e}")
        return

    if not memory:
        return

    lines = [
        "\n\n---\n",
        "**長期記憶（系統自動注入，跨 session 保留）**\n",
    ]
    for topic, data in memory.items():
        lines.append(f"- **{topic}**：{data['content']}")

    with open(soul_path, "a", encoding="utf-8") as f:
        f.write("\n".join(lines))

    logger.info(f"💾 已注入 {len(memory)} 條長期記憶至 SOUL.md")


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
    inject_memory_to_soul()
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
