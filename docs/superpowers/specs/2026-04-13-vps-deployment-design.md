# AI Secretary — GCE VPS 部署設計

**日期：** 2026-04-13
**目標：** 讓 AI Secretary（Hermes Agent 架構）在 GCE VM（us-west1-b）上端對端運行
**方案：** Git Push → deploy_vps.sh 一鍵部署

---

## 1. 整體架構與資料流

```
[仁哥 Telegram]
      ↓ (webhook HTTPS)
[Cloudflare Tunnel]   ← 免費、無需域名、自動 HTTPS (*.trycloudflare.com)
      ↓ (localhost:8080)
[hermes gateway]      ← 接收 Telegram 訊息、呼叫 LLM
      ↓
[Gemini 2.5 Flash]    ← 意圖理解與回覆生成
      ↓
[~/.hermes/skills/google_workspace_skills.py]  ← 技能執行層
      ↓
[Google APIs: Calendar / Gmail / Drive / Tasks / Contacts]
      ↓
回覆 → hermes → Cloudflare Tunnel → Telegram → 仁哥
```

### VM 上的檔案結構

```
~/ai-secretary/                  ← git clone from GitHub (private repo)
    main.py
    google_workspace_skills.py
    *_service.py
    .env                         ← 手動 SCP（不進 git）
    credentials.json             ← 手動 SCP（不進 git）
    token.json                   ← 手動 SCP（不進 git）
    venv/                        ← Python 虛擬環境

~/.hermes/
    config.yaml                  ← 部署腳本自動生成
    SOUL.md                      ← 從 persona_soul.md 複製
    skills/
        google_workspace_skills.py  ← 從專案複製
```

---

## 2. 部署流程

### 前置作業（本機一次性）

1. 確認 `.env` / `credentials.json` / `token.json` 備妥
2. Push 最新 code 到 GitHub private repo（VM 使用 Personal Access Token 拉取）
3. SCP 三個敏感檔案至 VM：
   ```bash
   scp .env credentials.json token.json <user>@<vm-ip>:~/ai-secretary/
   ```

### `deploy_vps.sh` 執行步驟（VM 上執行一次）

| Step | 內容 |
|------|------|
| 1 | 系統依賴檢查（Python 3.11+, git, curl） |
| 2 | clone 或 git pull GitHub repo |
| 3 | Python venv + `pip install -r requirements.txt` + `pip install hermes-agent` |
| 4 | 安裝 cloudflared（官方 .deb） |
| 5 | 啟動 cloudflared tunnel → 取得 `*.trycloudflare.com` URL |
| 6 | 生成 `~/.hermes/config.yaml`（寫入 Gemini key、Telegram token、tunnel URL） |
| 7 | 複製 `persona_soul.md` → `~/.hermes/SOUL.md`，複製 skills |
| 8 | 向 Telegram 註冊 webhook（`curl` setWebhook API） |
| 9 | 建立並啟用 systemd 服務 `ai-secretary.service` |
| 10 | 啟動服務並印出健康狀態 |

### 日後更新

```bash
cd ~/ai-secretary && git pull && sudo systemctl restart ai-secretary
```

---

## 3. `~/.hermes/config.yaml` 結構

```yaml
model: gemini:gemini-2.5-flash

platforms:
  telegram:
    token: "${TELEGRAM_BOT_TOKEN}"
    webhook_url: "${CLOUDFLARE_TUNNEL_URL}"
    allowed_chat_ids:
      - "${TELEGRAM_CHAT_ID}"

skills_dir: ~/.hermes/skills
soul_file: ~/.hermes/SOUL.md

google:
  credentials_file: ~/ai-secretary/credentials.json
  token_file: ~/ai-secretary/token.json
```

- `allowed_chat_ids`：只有仁哥的 chat_id 可觸發 agent，其他訊息忽略

---

## 4. systemd 服務

```ini
# /etc/systemd/system/ai-secretary.service
# <vm_user> 由 deploy_vps.sh 執行時自動偵測（whoami）並填入
[Unit]
Description=AI Secretary (Hermes Agent)
After=network-online.target

[Service]
User=<vm_user>
WorkingDirectory=/home/<vm_user>/ai-secretary
EnvironmentFile=/home/<vm_user>/ai-secretary/.env
ExecStart=/home/<vm_user>/ai-secretary/venv/bin/python main.py
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

- 崩潰後 10 秒自動重啟
- 日誌查看：`journalctl -u ai-secretary -f`

### Cloudflare Tunnel URL 變動問題

`trycloudflare.com` 的免費 tunnel URL 每次重啟會改變，導致 Telegram webhook 失效。解法：

- `main.py` 啟動時自動讀取當前 tunnel URL 並呼叫 Telegram `setWebhook` API 更新
- 或在 `deploy_vps.sh` 中，每次啟動 cloudflared 後立即重新執行 setWebhook

---

## 5. Google Auth 處理

- `token.json` 包含 OAuth refresh token，直接從本機 SCP 至 VM 沿用，不需重跑授權流程
- **Token 過期處理順序**：
  1. 在本機確認 token 有效（執行任一 Google API 呼叫測試）
  2. 若已過期，本機執行 `update_auth_and_cloud.py` 重新取得 token
  3. SCP 新的 `token.json` 至 VM：`scp token.json <user>@<vm-ip>:~/ai-secretary/`
  4. `sudo systemctl restart ai-secretary`

---

## 6. 不在本次範圍內

- `shared/line_responder.py` 舊 LINE 殘留清理（可後續處理）
- `alice/` / `birdie/` 空目錄確認（Hermes 架構下不需要）
- NotebookLM 技能整合（需另行設計）
