# VPS 部署 (Hermes Agent + Cloudflare Tunnel) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 讓 AI Secretary 在 GCE VM 上端對端運行：cloudflared 提供 HTTPS tunnel，main.py 自動取得 URL 並向 Telegram 註冊 webhook，hermes-agent 處理 LLM 對話。

**Architecture:** `main.py` 啟動時管理 cloudflared 子程序、解析 tunnel URL、呼叫 Telegram setWebhook、再啟動 hermes gateway。`deploy_vps.sh` 補齊 cloudflared 安裝、`~/.hermes/config.yaml` 生成、修正 systemd ExecStart 指向 `main.py`。

**Tech Stack:** Python 3.11, hermes-agent (pip), cloudflared (free tunnel), Telegram Bot API, systemd, GCE VM us-west1-b

---

## 現況差距分析（deploy_vps.sh）

| 項目 | 現況 | 需要 |
|------|------|------|
| hermes-agent 安裝 | ✅ curl install.sh（但繞過 venv） | 改用 pip install（已在 requirements.txt） |
| cloudflared 安裝 | ❌ 缺失 | 需新增 |
| ~/.hermes/config.yaml | ❌ 缺失 | 需生成 |
| systemd ExecStart | ⚠️ Python wrapper 繞過 main.py | 改為 `python main.py` |
| Telegram webhook | ❌ 無 | 由 main.py 啟動時自動處理 |

---

## File Map

| 檔案 | 動作 | 說明 |
|------|------|------|
| `main.py` | MODIFY | 新增 `parse_cloudflare_url`、`register_webhook`、`start_cloudflared` 函數；`main()` 統一協調 |
| `deploy_vps.sh` | MODIFY | 移除 curl install.sh、新增 cloudflared 安裝、生成 config.yaml、修正 systemd ExecStart |
| `tests/__init__.py` | CREATE | test package |
| `tests/test_main.py` | CREATE | 純函數單元測試 |

---

## Task 1：重構 main.py — cloudflared 管理與 webhook 自動註冊（TDD）

**Files:**
- Modify: `main.py`
- Create: `tests/__init__.py`
- Create: `tests/test_main.py`

- [ ] **Step 1：建立 tests 目錄與空 __init__.py**

```bash
mkdir -p tests
touch tests/__init__.py
```

- [ ] **Step 2：寫失敗測試**

建立 `tests/test_main.py`：

```python
"""tests/test_main.py — main.py 純函數單元測試"""
from unittest.mock import patch, MagicMock


def test_parse_cloudflare_url_found():
    """cloudflared 輸出行含 URL 時應解析並回傳"""
    from main import parse_cloudflare_url

    line = "INF +----------------------------+ https://abc-def-123.trycloudflare.com"
    assert parse_cloudflare_url(line) == "https://abc-def-123.trycloudflare.com"


def test_parse_cloudflare_url_not_found():
    """不含 URL 的行應回傳 None"""
    from main import parse_cloudflare_url

    assert parse_cloudflare_url("INF Starting tunnel connection") is None


def test_register_webhook_success():
    """Telegram 回傳 ok:true 時應回傳 True"""
    from main import register_webhook

    mock_resp = MagicMock()
    mock_resp.json.return_value = {"ok": True}

    with patch("main.requests.post", return_value=mock_resp):
        assert register_webhook("fake-token", "https://abc.trycloudflare.com") is True


def test_register_webhook_failure():
    """Telegram 回傳 ok:false 時應回傳 False"""
    from main import register_webhook

    mock_resp = MagicMock()
    mock_resp.json.return_value = {"ok": False, "description": "Bad Request"}

    with patch("main.requests.post", return_value=mock_resp):
        assert register_webhook("fake-token", "https://abc.trycloudflare.com") is False


def test_register_webhook_exception():
    """requests 拋出例外時應回傳 False 而非崩潰"""
    from main import register_webhook

    with patch("main.requests.post", side_effect=ConnectionError("timeout")):
        assert register_webhook("fake-token", "https://abc.trycloudflare.com") is False
```

- [ ] **Step 3：執行測試，確認失敗**

```bash
pip install pytest
pytest tests/test_main.py -v
```

Expected: `ImportError: cannot import name 'parse_cloudflare_url' from 'main'`

- [ ] **Step 4：用以下內容完整取代 main.py**

```python
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


def register_webhook(bot_token: str, tunnel_url: str) -> bool:
    """向 Telegram 註冊 webhook，成功回傳 True，失敗回傳 False。"""
    endpoint = f"{tunnel_url}/webhook"
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
        logger.error(f"❌ Webhook 註冊失敗：{result.get('description')}")
        return False
    except Exception as e:
        logger.error(f"❌ Webhook 註冊例外：{e}")
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

    threading.Thread(target=_reader, daemon=True).start()

    if not found.wait(timeout=30):
        proc.terminate()
        raise RuntimeError("cloudflared 未能在 30 秒內提供 tunnel URL")

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
    except RuntimeError as e:
        logger.error(str(e))
        sys.exit(1)

    logger.info(f"🌐 Tunnel URL：{tunnel_url}")

    if not register_webhook(Config.TELEGRAM_BOT_TOKEN, tunnel_url):
        logger.warning("⚠️  Webhook 未成功註冊，繼續啟動（可手動重試）")

    logger.info("🤖 啟動 Hermes Gateway...")
    try:
        subprocess.run(["hermes", "gateway", "start"], check=True)
    except FileNotFoundError:
        logger.error("找不到 hermes 指令，請確認已安裝 hermes-agent 套件。")
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("收到中斷訊號，正在關閉...")
    finally:
        logger.info("關閉 cloudflared...")
        cf_proc.terminate()
        cf_proc.wait(timeout=5)


if __name__ == "__main__":
    main()
```

- [ ] **Step 5：執行測試，確認全部通過**

```bash
pytest tests/test_main.py -v
```

Expected:
```
tests/test_main.py::test_parse_cloudflare_url_found PASSED
tests/test_main.py::test_parse_cloudflare_url_not_found PASSED
tests/test_main.py::test_register_webhook_success PASSED
tests/test_main.py::test_register_webhook_failure PASSED
tests/test_main.py::test_register_webhook_exception PASSED

5 passed
```

- [ ] **Step 6：Commit**

```bash
git add main.py tests/__init__.py tests/test_main.py
git commit -m "feat: main.py 整合 cloudflared 管理與 Telegram webhook 自動註冊"
```

---

## Task 2：更新 deploy_vps.sh — 補齊三個缺口

**Files:**
- Modify: `deploy_vps.sh`

缺口一：Step 4 的 curl install.sh 繞過 venv，改用 pip（已在 requirements.txt）。
缺口二：缺少 cloudflared 安裝。
缺口三：systemd ExecStart 需改為 `python main.py`；同時加入 config.yaml 生成。

- [ ] **Step 1：將 Step 4（hermes 安裝）替換為 pip 確認**

找到以下區塊：

```bash
# ── Step 4: 安裝 Hermes Agent ─────────────────────────────
echo ""
echo "🤖 Step 4: 安裝 / 更新 Hermes Agent..."

if ! command -v hermes &> /dev/null; then
    echo "  首次安裝 Hermes Agent..."
    curl -fsSL https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.sh | bash
    source ~/.bashrc
else
    echo "  更新 Hermes Agent..."
    hermes update || true
fi
```

替換為：

```bash
# ── Step 4: 確認 hermes-agent 已透過 pip 安裝 ────────────────
echo ""
echo "🤖 Step 4: 確認 hermes-agent..."

if ! "$APP_DIR/venv/bin/hermes" --version &> /dev/null 2>&1; then
    echo "  安裝 hermes-agent 至 venv..."
    "$APP_DIR/venv/bin/pip" install hermes-agent -q
fi
echo "  hermes-agent 已就緒。"
```

- [ ] **Step 2：在 Step 5 之前插入 cloudflared 安裝區塊**

在 `# ── Step 5: 建立持久化目錄` 之前，插入：

```bash
# ── Step 4b: 安裝 cloudflared ─────────────────────────────
echo ""
echo "🚇 Step 4b: 安裝 cloudflared..."

if ! command -v cloudflared &> /dev/null; then
    curl -fsSL https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb \
        -o /tmp/cloudflared.deb
    sudo dpkg -i /tmp/cloudflared.deb
    rm -f /tmp/cloudflared.deb
    echo "  cloudflared 安裝完成。"
else
    echo "  cloudflared 已存在，跳過。"
fi
```

- [ ] **Step 3：在 Step 6 之後插入 config.yaml 生成區塊**

在 `# ── Step 7: 設定 Google Workspace 技能` 之前，插入：

```bash
# ── Step 6b: 生成 ~/.hermes/config.yaml ──────────────────
echo ""
echo "⚙️  Step 6b: 生成 Hermes 設定檔..."

# 載入 .env 取得 token 值
set -o allexport
source "$APP_DIR/.env"
set +o allexport

cat > "$HERMES_DIR/config.yaml" << HEREDOC
model: gemini:gemini-2.5-flash

platforms:
  telegram:
    token: "${TELEGRAM_BOT_TOKEN}"
    webhook_url: "https://placeholder.trycloudflare.com"
    allowed_chat_ids:
      - "${TELEGRAM_CHAT_ID}"

skills_dir: ${HERMES_DIR}/skills
soul_file: ${HERMES_DIR}/SOUL.md
HEREDOC

echo "  config.yaml 已生成（webhook_url 將由 main.py 啟動時自動更新）。"
```

- [ ] **Step 4：修正 Step 10 的 systemd ExecStart**

找到 systemd ExecStart 這行：

```bash
ExecStart=$APP_DIR/venv/bin/python -c "import subprocess; subprocess.run(['hermes', 'gateway', 'start'])"
```

替換為：

```bash
ExecStart=$APP_DIR/venv/bin/python $APP_DIR/main.py
```

同時，找到 `Environment=PATH=...` 區塊，在其後加入：

```bash
Environment=PYTHONPATH=$APP_DIR
```

- [ ] **Step 5：驗證 deploy_vps.sh 語法**

```bash
bash -n deploy_vps.sh
```

Expected: 無輸出（無語法錯誤）

- [ ] **Step 6：Commit**

```bash
git add deploy_vps.sh
git commit -m "feat: deploy_vps.sh 補齊 cloudflared 安裝、config.yaml 生成、修正 systemd ExecStart"
```

---

## Task 3：Push 並上傳敏感檔案至 VM

**Files:**（無程式碼變更，操作步驟）

- [ ] **Step 1：Push 至 GitHub**

```bash
git push origin master
```

Expected: `master -> master` 推送成功

- [ ] **Step 2：取得 VM 外部 IP**

```bash
gcloud compute instances describe instance-20260412-125252 \
  --zone=us-west1-b \
  --format="get(networkInterfaces[0].accessConfigs[0].natIP)"
```

記下輸出的 IP（以下用 `$VM_IP` 代替）。

- [ ] **Step 3：SCP 敏感檔案至 VM**

```bash
VM_USER=<你的 GCE 使用者名稱>
VM_IP=<上一步取得的 IP>

scp .env credentials.json token.json \
    "${VM_USER}@${VM_IP}:~/ai-secretary/"
```

Expected: 三個檔案傳輸完成，無錯誤。

- [ ] **Step 4：SSH 確認檔案到位**

```bash
ssh "${VM_USER}@${VM_IP}" \
  "ls -la ~/ai-secretary/.env ~/ai-secretary/credentials.json ~/ai-secretary/token.json"
```

Expected: 三個檔案均存在且有讀取權限。

---

## Task 4：在 VM 執行部署並端對端驗證

**Files:**（VM 上操作）

- [ ] **Step 1：SSH 進 VM**

```bash
ssh "${VM_USER}@${VM_IP}"
```

- [ ] **Step 2：首次部署（若 repo 尚不存在）**

```bash
cd ~
git clone https://github.com/zing1971/ai-secretary.git
```

若 repo 已存在則略過，deploy_vps.sh 會自動 git pull。

- [ ] **Step 3：執行部署腳本**

```bash
cd ~/ai-secretary
bash deploy_vps.sh
```

Expected 結尾輸出：
```
✅ ai-secretary 服務已設定並啟用開機自啟。

==========================================
  ✅ 部署完成！
==========================================
```

- [ ] **Step 4：啟動服務**

```bash
sudo systemctl start ai-secretary
sleep 8
sudo systemctl status ai-secretary
```

Expected: `Active: active (running)`

- [ ] **Step 5：確認 cloudflared 與 webhook 成功**

```bash
journalctl -u ai-secretary -n 30 --no-pager
```

Expected 日誌中依序出現：
```
🚇 啟動 cloudflared tunnel (→ localhost:8080)...
🌐 Tunnel URL：https://xxxx.trycloudflare.com
✅ Webhook 已註冊：https://xxxx.trycloudflare.com/webhook
🤖 啟動 Hermes Gateway...
```

- [ ] **Step 6：Telegram 端對端測試**

在 Telegram 向 Bot 傳送：`早安`

Expected：Bot 回覆今日行程或 Google 服務摘要（若 token.json 有效）。
若 token 失效，Bot 應回覆錯誤提示而非無回應。

- [ ] **Step 7：確認重啟後 webhook 自動更新**

```bash
sudo systemctl restart ai-secretary
sleep 10
journalctl -u ai-secretary -n 10 --no-pager | grep "Webhook"
```

Expected：出現新的 `trycloudflare.com` URL 且 `✅ Webhook 已註冊`（URL 與重啟前不同）。

---

## 注意事項

**hermes config.yaml 格式：** `allowed_chat_ids`、`skills_dir`、`soul_file` 等鍵名需在安裝 hermes-agent 後確認是否與實際文件吻合。若 hermes 不支援某鍵，移除即可，不影響啟動。

**GitHub repo 存取：** 若為私有 repo，VM 需設定 Personal Access Token（`git remote set-url origin https://<PAT>@github.com/zing1971/ai-secretary.git`）或 SSH key。
