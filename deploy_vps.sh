#!/bin/bash
# =====================================================
# AI Secretary (Hermes Agent) - VPS 部署腳本
# 用法：在 VPS 上執行 bash deploy_vps.sh
# =====================================================
set -e

APP_DIR="$HOME/ai-secretary"
HERMES_DIR="$HOME/.hermes"
REPO_URL="https://github.com/zing1971/ai-secretary.git"

echo "=========================================="
echo "  AI Secretary - Hermes Agent 部署腳本"
echo "=========================================="

# ── Step 1: 系統環境準備 ──────────────────────────────────
echo ""
echo "📦 Step 1: 檢查系統依賴..."

# 確保 Python 3.11+ 可用
if ! command -v python3 &> /dev/null; then
    echo "❌ 找不到 python3，正在安裝..."
    sudo apt-get update && sudo apt-get install -y python3 python3-pip python3-venv
fi

PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo "  Python 版本: $PYTHON_VERSION"

# 確保 git 可用
if ! command -v git &> /dev/null; then
    sudo apt-get install -y git
fi

# ── Step 2: 拉取程式碼 ────────────────────────────────────
echo ""
echo "📥 Step 2: 設定程式碼..."

if [ -d "$APP_DIR/.git" ]; then
    echo "  已有 repo，拉取最新版本..."
    cd "$APP_DIR"
    git pull origin master
else
    echo "  首次部署，從 GitHub 克隆..."
    git clone "$REPO_URL" "$APP_DIR"
    cd "$APP_DIR"
fi

# ── Step 3: Python 虛擬環境 ───────────────────────────────
echo ""
echo "🐍 Step 3: 設定 Python 虛擬環境..."

if [ ! -d "$APP_DIR/venv" ]; then
    python3 -m venv "$APP_DIR/venv"
    echo "  虛擬環境已建立。"
fi

source "$APP_DIR/venv/bin/activate"
pip install --upgrade pip -q
pip install -r requirements.txt -q
echo "  依賴安裝完成。"

# ── Step 4: 確認 hermes-agent 已透過 pip 安裝 ────────────────
echo ""
echo "🤖 Step 4: 確認 hermes-agent..."

if ! "$APP_DIR/venv/bin/hermes" --version &> /dev/null; then
    echo "  安裝 hermes-agent 至 venv..."
    "$APP_DIR/venv/bin/pip" install hermes-agent -q
fi
echo "  hermes-agent 已就緒。"

# ── Step 5: 建立持久化目錄 ─────────────────────────────────
echo ""
echo "💾 Step 5: 確保持久化目錄存在..."

mkdir -p "$HERMES_DIR/skills"
mkdir -p "$HERMES_DIR/mcp"
echo "  $HERMES_DIR 已就緒。"

# ── Step 6: 設定 Persona ──────────────────────────────────
echo ""
echo "👩‍💼 Step 6: 部署 Persona 設定..."

if [ -f "$APP_DIR/persona_soul.md" ]; then
    cp "$APP_DIR/persona_soul.md" "$HERMES_DIR/SOUL.md"
    echo "  SOUL.md 已同步。"
fi

# ── Step 6b: 生成 ~/.hermes/config.yaml ──────────────────
echo ""
echo "⚙️  Step 6b: 生成 Hermes 設定檔..."

if [ ! -f "$APP_DIR/.env" ]; then
    echo "  ⚠️ 找不到 .env，跳過 config.yaml 生成（將於 Step 8 中止）"
else
    set -o allexport
    source "$APP_DIR/.env"
    set +o allexport

    cat > "$HERMES_DIR/config.yaml" << HEREDOC
model: gemini-2.5-flash

platforms:
  telegram:
    token: "${TELEGRAM_BOT_TOKEN}"

skills_dir: '${HERMES_DIR}/skills'
soul_file: '${HERMES_DIR}/SOUL.md'

# 為 telegram 平台明確啟用需要的 toolsets
platform_toolsets:
  telegram:
    - terminal
    - file
    - skills
    - web
    - memory
    - todo
    - vision
HEREDOC

    echo "  config.yaml 已生成（terminal toolset 已啟用）。"
fi

# ── Step 6c: 生成 ~/.hermes/.env（用戶白名單）────────────────
echo ""
echo "⚙️  Step 6c: 生成 Hermes 用戶白名單設定..."

if [ -f "$APP_DIR/.env" ]; then
    set -o allexport
    source "$APP_DIR/.env"
    set +o allexport

    cat > "$HERMES_DIR/.env" << HEREDOC
TELEGRAM_ALLOWED_USERS=${TELEGRAM_CHAT_ID}
GATEWAY_ALLOW_ALL_USERS=true
HEREDOC
    echo "  ~/.hermes/.env 已生成（TELEGRAM_ALLOWED_USERS=${TELEGRAM_CHAT_ID}）。"
else
    echo "  ⚠️ 找不到 .env，跳過 ~/.hermes/.env 生成。"
fi

# ── Step 7: 部署 alice CLI 工具 ──────────────────────────────
echo ""
echo "🔧 Step 7: 部署 alice CLI 工具..."

# 確保 bin/ 目錄存在並有執行權限
chmod +x "$APP_DIR/bin/alice"
chmod +x "$APP_DIR/bin/alice_tools.py"
echo "  bin/alice 與 bin/alice_tools.py 已設定執行權限。"

# 移除舊的扁平式技能檔案（前版遺留，已不使用）
rm -f "$HERMES_DIR/skills/google_workspace_skills.py"
rm -f "$HERMES_DIR/skills/calendar_skills.py"
rm -f "$HERMES_DIR/skills/gmail_skills.py"
rm -f "$HERMES_DIR/skills/tasks_skills.py"
rm -f "$HERMES_DIR/skills/drive_skills.py"
rm -f "$HERMES_DIR/skills/contacts_skills.py"
rm -f "$HERMES_DIR/skills/generation_skills.py"
rm -f "$HERMES_DIR/skills/memory_skills.py"
rm -f "$HERMES_DIR/skills/_skill_base.py"
echo "  舊版扁平式技能檔案已清除。"

# 建立 ai-secretary skill 套件（hermes 用 SKILL.md 識別）
SKILL_DIR="$HERMES_DIR/skills/ai-secretary"
mkdir -p "$SKILL_DIR"

cat > "$SKILL_DIR/SKILL.md" << 'SKILL_EOF'
---
name: ai-secretary
description: Alice's personal toolset for Google Workspace (Calendar, Gmail, Tasks, Drive, Contacts), Gemini Pro generation, and cross-session memory.
version: 1.0.0
author: zing1971
---

# AI Secretary Tools

Alice 透過 `terminal` 工具執行 `alice` 命令來操作 Google Workspace。

## 命令前綴

```bash
# alice 命令已加入 PATH，可直接呼叫
alice <domain> <action> [--arg value ...]
```

## 行事曆（Calendar）

```bash
alice calendar list
alice calendar create --title "週會" --start "2026-04-20 10:00" --end "2026-04-20 11:00"
alice calendar create --title "週會" --start "2026-04-20 10:00" --end "2026-04-20 11:00" --location "會議室 A" --desc "備註"
alice calendar create --title "休假" --start "2026-04-25" --end "2026-04-26"
```

## 信件（Gmail）

```bash
alice gmail search
alice gmail search --query "is:unread" --max 10
alice gmail draft --to "user@example.com" --subject "主旨" --body "內文（換行用 \n）"
```

## 待辦事項（Tasks）

```bash
alice tasks list
alice tasks add --title "任務標題"
alice tasks add --title "任務標題" --notes "備註" --due "2026-05-01T23:59:59Z"
```

## 雲端硬碟（Drive）

```bash
alice drive search --keyword "關鍵字" --max 5
```

## 聯絡人（Contacts）

```bash
alice contacts search --query "姓名或公司"
alice contacts create --name "姓名" --email "email@example.com" --phone "手機" --company "公司" --title "職稱" --label "廠商代表"
```

可用標籤：政府機關、學術研究、廠商代表、關鍵夥伴、媒體公關、其他

## 起草專業內容（Generate）

使用 Gemini 2.5 Pro 生成高品質正式內容。

```bash
alice generate --task "任務描述"
alice generate --task "起草感謝信給王大明董事長" --context "上週在投資論壇引薦了三位重要人士"
```

## 長期記憶（Memory）

```bash
alice memory remember --topic "主題" --content "內容"
alice memory recall
alice memory recall --query "關鍵字"
alice memory forget --topic "主題"
```
SKILL_EOF

echo "  ~/.hermes/skills/ai-secretary/SKILL.md 已建立。"

# 將 ai-secretary 以 editable 模式安裝至 hermes 的 venv，
# 讓 alice_tools.py 可以 import google_auth / gmail_service 等服務模組。
HERMES_PYTHON="$HERMES_DIR/hermes-agent/venv/bin/python3"
if [ -f "$HERMES_PYTHON" ]; then
    echo "  以 pip install -e 將 ai-secretary 安裝至 hermes venv..."
    "$HERMES_PYTHON" -m pip install --quiet -e "$APP_DIR"
    echo "  ✅ ai-secretary 套件安裝完成（editable 模式）。"
else
    echo "  ⚠️ 找不到 hermes venv ($HERMES_PYTHON)，跳過套件安裝。"
fi

# ── Step 8: 環境變數檢查 ──────────────────────────────────
echo ""
echo "🔑 Step 8: 檢查環境變數..."

if [ ! -f "$APP_DIR/.env" ]; then
    echo "  ⚠️ 找不到 .env 檔案！"
    echo "  請從 .env.example 複製並填入正確的值："
    echo "    cp .env.example .env"
    echo "    nano .env"
    echo ""
    echo "  部署腳本先行中止，待 .env 設定完成後再次執行。"
    exit 1
fi

# 載入 .env 並做基本驗證
set -o allexport
source "$APP_DIR/.env"
set +o allexport

MISSING=""
[ -z "$TELEGRAM_BOT_TOKEN" ] && MISSING="$MISSING TELEGRAM_BOT_TOKEN"
[ -z "$TELEGRAM_CHAT_ID" ] && MISSING="$MISSING TELEGRAM_CHAT_ID"
[ -z "$GEMINI_API_KEY" ] && MISSING="$MISSING GEMINI_API_KEY"

if [ -n "$MISSING" ]; then
    echo "  ❌ 缺少必要環境變數:$MISSING"
    echo "  請編輯 .env 後再次執行部署。"
    exit 1
fi

echo "  ✅ 環境變數驗證通過。"

# ── Step 9: 設定 token.json ───────────────────────────────
echo ""
echo "🔐 Step 9: 檢查 Google OAuth Token..."

if [ ! -f "$APP_DIR/token.json" ]; then
    echo "  ⚠️ 找不到 token.json！"
    echo "  Google Workspace 技能將無法使用。"
    echo "  請在本地執行授權後將 token.json 上傳至 $APP_DIR/"
    echo "  (scp token.json user@vps:~/ai-secretary/)"
else
    echo "  ✅ token.json 已存在。"
fi

# ── Step 10: 建立 systemd 服務 ─────────────────────────────
echo ""
echo "⚙️ Step 10: 設定 systemd 服務以確保開機自啟..."

SERVICE_FILE="/etc/systemd/system/ai-secretary.service"

sudo tee "$SERVICE_FILE" > /dev/null << EOF
[Unit]
Description=AI Secretary (Hermes Agent)
After=network.target
StartLimitIntervalSec=300
StartLimitBurst=3

[Service]
Type=simple
User=$USER
WorkingDirectory=$APP_DIR
EnvironmentFile=$APP_DIR/.env
ExecStart=$APP_DIR/venv/bin/python $APP_DIR/main.py
Restart=on-failure
RestartSec=60

# 確保 Hermes 目錄存在
ExecStartPre=/bin/mkdir -p $HERMES_DIR

# 環境變數
Environment=HERMES_MODEL=gemini-2.5-flash
# alice 命令與 hermes venv 均加入 PATH，讓 terminal tool 可直接呼叫
Environment=PATH=/home/$USER/ai-secretary/bin:/home/$USER/.hermes/hermes-agent/venv/bin:/home/$USER/.local/bin:/usr/local/bin:/usr/bin:/bin
Environment=PYTHONPATH=$APP_DIR

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable ai-secretary
echo "  ✅ systemd 服務已設定並啟用開機自啟。"

echo ""
echo "=========================================="
echo "  ✅ 部署完成！"
echo "=========================================="
echo ""
echo "  操作指引："
echo "  ├─ 啟動服務:  sudo systemctl start ai-secretary"
echo "  ├─ 停止服務:  sudo systemctl stop ai-secretary"
echo "  ├─ 查看狀態:  sudo systemctl status ai-secretary"
echo "  ├─ 查看日誌:  journalctl -u ai-secretary -f"
echo "  └─ 更新部署:  cd ~/ai-secretary && git pull && bash deploy_vps.sh"
echo ""
echo "  首次啟動請執行: sudo systemctl start ai-secretary"
echo ""
