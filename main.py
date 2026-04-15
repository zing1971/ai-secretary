"""
AI Secretary (Hermes Agent 架構) - 入口點

啟動順序：
1. 驗證環境變數
2. 同步 persona_soul.md → ~/.hermes/SOUL.md
3. 啟動 cloudflared tunnel（子程序），解析公開 HTTPS URL
4. 向 Telegram 註冊 webhook
5. 啟動 hermes gateway start（阻塞）
6. 結束時終止 cloudflared
"""
import os
import re
import sys
import shutil
import subprocess
import threading
import logging
import time
import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("AI-Secretary")

_CF_URL_RE = re.compile(r"https://[a-z0-9\-]+\.trycloudflare\.com")


def parse_cloudflare_url(line: str) -> str | None:
    """從 cloudflared 輸出的一行文字解析 tunnel URL，找不到回傳 None。"""
    m = _CF_URL_RE.search(line)
    return m.group(0) if m else None


def update_hermes_webhook_url(tunnel_url: str) -> None:
    """更新 ~/.hermes/config.yaml 的 webhook_url 為實際 tunnel URL。"""
    config_path = os.path.expanduser("~/.hermes/config.yaml")
    if not os.path.exists(config_path):
        logger.warning(f"找不到 {config_path}，跳過 webhook_url 更新")
        return
    with open(config_path, "r") as f:
        content = f.read()
    webhook_url = f"{tunnel_url}/webhook"
    new_content = re.sub(
        r'webhook_url:\s*"[^"]*"',
        f'webhook_url: "{webhook_url}"',
        content,
    )
    with open(config_path, "w") as f:
        f.write(new_content)
    logger.info(f"📝 config.yaml webhook_url 已更新：{webhook_url}")


def register_webhook(
    bot_token: str, tunnel_url: str, max_retries: int = 3, retry_delay: float = 5.0
) -> bool:
    """向 Telegram 註冊 webhook，支援重試。成功回傳 True，失敗回傳 False。"""
    endpoint = f"{tunnel_url}/webhook"
    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.post(
                f"https://api.telegram.org/bot{bot_token}/setWebhook",
                json={"url": endpoint},
                timeout=15,
            )
            result = resp.json()
            if result.get("ok"):
                logger.info(f"✅ Webhook 已註冊：{endpoint}")
                return True
            desc = result.get("description", "unknown error")
            logger.warning(f"⚠️  Webhook 第 {attempt} 次嘗試失敗：{desc}")
        except Exception as e:
            logger.warning(f"⚠️  Webhook 第 {attempt} 次嘗試例外：{e}")
        if attempt < max_retries:
            logger.info(f"   {retry_delay:.0f}s 後重試...")
            time.sleep(retry_delay)
    logger.error(f"❌ Webhook 註冊失敗（已重試 {max_retries} 次）")
    return False


def start_cloudflared(port: int) -> tuple:
    """
    啟動 cloudflared tunnel 子程序，等待取得公開 URL。

    Args:
        port: hermes gateway 監聽的本地 port

    Returns:
        (subprocess.Popen, tunnel_url: str)

    Raises:
        RuntimeError: 若 30 秒內未能取得 URL
    """
    proc = subprocess.Popen(
        ["cloudflared", "tunnel", "--url", f"http://localhost:{port}", "--no-autoupdate"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    found = threading.Event()
    holder = [None]

    def _reader():
        for line in proc.stdout:
            logger.debug(f"cloudflared: {line.rstrip()}")
            url = parse_cloudflare_url(line)
            if url:
                holder[0] = url
                found.set()
                # 繼續消費 stdout 防止 buffer 塞滿
                for _ in proc.stdout:
                    pass
                return
        # stdout 關閉但未找到 URL（程序提早結束）
        found.set()  # 解除主執行緒等待，holder[0] 仍為 None

    threading.Thread(target=_reader, daemon=True).start()

    if not found.wait(timeout=30):
        proc.terminate()
        raise RuntimeError("cloudflared 未能在 30 秒內提供 tunnel URL")

    if holder[0] is None:
        # 程序在提供 URL 之前異常結束
        proc.wait()
        raise RuntimeError(f"cloudflared 異常結束（return code: {proc.returncode}），未能取得 tunnel URL")

    return proc, holder[0]


def sync_persona():
    """複製 persona_soul.md 至 ~/.hermes/SOUL.md。"""
    hermes_dir = os.path.expanduser("~/.hermes")
    os.makedirs(hermes_dir, exist_ok=True)
    src = os.path.join(os.path.dirname(__file__), "persona_soul.md")
    dst = os.path.join(hermes_dir, "SOUL.md")
    if os.path.exists(src):
        shutil.copy2(src, dst)
        logger.info(f"Persona 已同步至 {dst}")


def main():
    from config import Config

    if not Config.validate():
        logger.error("環境變數驗證失敗，無法啟動。")
        sys.exit(1)

    sync_persona()

    logger.info(f"🚇 啟動 cloudflared tunnel (→ localhost:{Config.PORT})...")
    try:
        cf_proc, tunnel_url = start_cloudflared(Config.PORT)
    except FileNotFoundError:
        logger.error("找不到 cloudflared 指令，請確認已安裝 cloudflared。")
        sys.exit(1)
    except RuntimeError as e:
        logger.error(str(e))
        sys.exit(1)

    logger.info(f"🌐 Tunnel URL：{tunnel_url}")
    update_hermes_webhook_url(tunnel_url)

    if not register_webhook(Config.TELEGRAM_BOT_TOKEN, tunnel_url):
        logger.warning("⚠️  Webhook 未成功註冊，繼續啟動（可手動重試）")

    logger.info("🤖 啟動 Hermes Gateway...")
    try:
        subprocess.run(["hermes", "gateway", "run"], check=True)
    except FileNotFoundError:
        logger.error("找不到 hermes 指令，請確認已安裝 hermes-agent 套件。")
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("收到中斷訊號，正在關閉...")
    finally:
        logger.info("關閉 cloudflared...")
        cf_proc.terminate()
        try:
            cf_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            cf_proc.kill()


if __name__ == "__main__":
    main()
