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

# ── Step 7: 設定 Google Workspace 技能 ─────────────────────
echo ""
echo "🔧 Step 7: 部署 Google Workspace 技能..."

cp "$APP_DIR/google_workspace_skills.py" "$HERMES_DIR/skills/"
echo "  技能已部署到 $HERMES_DIR/skills/"

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

[Service]
Type=simple
User=$USER
WorkingDirectory=$APP_DIR
EnvironmentFile=$APP_DIR/.env
ExecStart=$APP_DIR/venv/bin/python -c "import subprocess; subprocess.run(['hermes', 'gateway', 'start'])"
Restart=on-failure
RestartSec=10

# 確保 Hermes 目錄存在
ExecStartPre=/bin/mkdir -p $HERMES_DIR

# 環境變數
Environment=PYTHONPATH=$APP_DIR
Environment=HERMES_MODEL=gemini:gemini-2.5-flash
Environment=PATH=$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin

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
