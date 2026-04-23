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
import re


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("AI-Secretary")


def patch_hermes_config() -> None:
    """
    強制覆寫 ~/.hermes/config.yaml 的 model 區段，確保使用正確的：
    - provider: gemini（Google AI Studio）
    - base_url: Google 的 OpenAI 相容端點（v1beta/openai）
    - model: gemini-1.5-flash
    - api_key: 從 GEMINI_API_KEY / GOOGLE_API_KEY 注入

    根本原因：Hermes 的 gemini provider 預設 base_url 為 v1beta（純 REST），
    但 Hermes 使用 OpenAI 格式發送請求，需改用 v1beta/openai 相容端點。
    """
    config_path = os.path.expanduser("~/.hermes/config.yaml")

    # 取得 API Key
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY", "")

    # 正確的 Google OpenAI 相容端點
    google_openai_base_url = "https://generativelanguage.googleapis.com/v1beta/openai"

    try:
        # 讀取現有設定（若存在）
        existing_content = ""
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                existing_content = f.read()

        # 強制覆寫 model 區段（保留其他設定不動）
        # 若已存在 model 區段則替換，否則在開頭插入
        model_block = (
            "model:\n"
            f"  default: gemini-1.5-flash\n"
            f"  provider: gemini\n"
            f"  base_url: {google_openai_base_url}\n"
            + (f"  api_key: {api_key}\n" if api_key else "")
        )

        # 使用正規表示式替換整個 model: 區段（多行匹配）
        # 匹配 model: 開頭直到下一個頂層 key（不含空格）或檔案結尾
        new_content = re.sub(
            r'^model:.*?(?=^\S|\Z)',
            model_block,
            existing_content,
            flags=re.MULTILINE | re.DOTALL
        )

        # 若原始內容中沒有 model: 區段，則在開頭加上
        if "model:" not in existing_content:
            new_content = model_block + "\n" + existing_content

        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        with open(config_path, "w", encoding="utf-8") as f:
            f.write(new_content)

        logger.info(
            f"🔧 已修復 ~/.hermes/config.yaml："
            f"provider=gemini, model=gemini-1.5-flash, base_url={google_openai_base_url}"
        )
    except Exception as e:
        logger.warning(f"⚠️  修復 config.yaml 時發生例外：{e}")


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

    patch_hermes_config()
    sync_persona()
    inject_memory_to_soul()

    # 處理未配對模式的特別說明
    if not Config.TELEGRAM_CHAT_ID:
        soul_path = os.path.expanduser("~/.hermes/SOUL.md")
        with open(soul_path, "a", encoding="utf-8") as f:
            f.write("\n\n---\n")
            f.write("**系統提示：目前處於「未配對模式」**\n")
            f.write("使用者尚未設定 TELEGRAM_CHAT_ID。如果使用者詢問自己的 ID，請查看訊息上下文中的 chat_id 並告知他們。\n")
            f.write("引導使用者將該 ID 填入 .env 檔案中的 TELEGRAM_CHAT_ID 欄位並重啟服務。\n")
        logger.warning("🕒 偵測到未配對，已將配對引導指令注入 SOUL.md")

    delete_webhook(Config.TELEGRAM_BOT_TOKEN)

    # 確保環境變數正確傳遞給子進程，強制使用 gemini provider
    env = os.environ.copy()
    env["GEMINI_API_KEY"] = Config.GEMINI_API_KEY
    env["GOOGLE_API_KEY"] = Config.GEMINI_API_KEY
    # HERMES_INFERENCE_PROVIDER 告訴 Hermes 使用 gemini provider
    env["HERMES_INFERENCE_PROVIDER"] = "gemini"
    # GEMINI_BASE_URL 覆寫 provider 預設 base_url，指向 OpenAI 相容端點
    env["GEMINI_BASE_URL"] = "https://generativelanguage.googleapis.com/v1beta/openai"
    env["LITELLM_LOGGING_LEVEL"] = "ERROR"
    env["PYTHONPATH"] = os.getcwd()

    logger.info("🤖 啟動 Hermes Gateway（polling 模式），使用 gemini provider + v1beta/openai 端點")
    
    try:
        subprocess.run(["hermes", "gateway", "run"], check=True, env=env)
    except FileNotFoundError:
        logger.error("找不到 hermes 指令，請確認已安裝 hermes-agent 套件。")
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        logger.error(f"hermes gateway 異常退出，return code: {e.returncode}")
        sys.exit(e.returncode)
    except KeyboardInterrupt:
        logger.info("收到中斷訊號，正在關閉...")


if __name__ == "__main__":
    main()
