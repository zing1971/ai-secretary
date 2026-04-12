"""
AI Secretary (Hermes Agent 架構) - 入口點
直接啟動 Hermes Gateway，使用 Telegram 進行長輪詢 (Long Polling) 通訊。
"""
import os
import sys
import subprocess
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("AI-Secretary")


def main():
    """啟動 Hermes Agent Gateway"""

    # 驗證必要環境變數
    from config import Config
    if not Config.validate():
        logger.error("環境變數驗證失敗，無法啟動。")
        sys.exit(1)

    # 複製 persona 設定到 Hermes 目錄
    hermes_dir = os.path.expanduser("~/.hermes")
    os.makedirs(hermes_dir, exist_ok=True)

    soul_src = os.path.join(os.path.dirname(__file__), "persona_soul.md")
    soul_dst = os.path.join(hermes_dir, "SOUL.md")
    if os.path.exists(soul_src):
        import shutil
        shutil.copy2(soul_src, soul_dst)
        logger.info(f"Persona 設定已同步至 {soul_dst}")

    logger.info("正在啟動 Hermes Gateway...")
    try:
        subprocess.run(["hermes", "gateway", "start"], check=True)
    except FileNotFoundError:
        logger.error("找不到 hermes 指令，請確認已安裝 hermes-agent 套件。")
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("收到中斷訊號，正在關閉...")


if __name__ == "__main__":
    main()
