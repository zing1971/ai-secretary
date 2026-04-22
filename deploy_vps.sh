#!/bin/bash
# =====================================================
# AI Secretary (Hermes Agent) - VPS Deployment Script
# =====================================================
set -e

APP_DIR="$HOME/ai-secretary"
HERMES_DIR="$HOME/.hermes"
REPO_URL="https://github.com/zing1971/ai-secretary.git"

echo "=========================================="
echo "  AI Secretary - Hermes Agent Deployment"
echo "=========================================="

# Step 1: Check System Dependencies
echo ""
echo "-> Step 1: Checking system dependencies..."

if ! command -v python3 &> /dev/null; then
    echo "  Installing python3..."
    sudo apt-get update && sudo apt-get install -y python3 python3-pip python3-venv
fi

PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo "  Python Version: $PYTHON_VERSION"

if ! command -v git &> /dev/null; then
    sudo apt-get install -y git
fi

# Step 2: Prepare Repository
echo ""
echo "-> Step 2: Preparing repository..."

if [ -d "$APP_DIR/.git" ]; then
    echo "  Repository exists. Updating..."
    cd "$APP_DIR"
    git pull origin master || echo "  Warning: git pull failed, continuing with local version."
else
    echo "  New deployment. Cloning from GitHub..."
    git clone "$REPO_URL" "$APP_DIR"
    cd "$APP_DIR"
fi

# Step 3: Setup Python Virtual Environment
echo ""
echo "-> Step 3: Setting up Python virtual environment..."

if [ ! -d "$APP_DIR/venv" ]; then
    python3 -m venv "$APP_DIR/venv"
    echo "  Virtual environment created."
fi

source "$APP_DIR/venv/bin/activate"
pip install --upgrade pip -q
pip install -r requirements.txt -q
echo "  Dependencies installed."

# Step 4: Install hermes-agent via pip
echo ""
echo "-> Step 4: Installing hermes-agent..."

if ! "$APP_DIR/venv/bin/hermes" --version &> /dev/null; then
    echo "  Installing hermes-agent into venv..."
    "$APP_DIR/venv/bin/pip" install hermes-agent -q
fi
echo "  hermes-agent is ready."

# Step 5: Initialize Hermes Directory
echo ""
echo "-> Step 5: Initializing hermes directory..."

mkdir -p "$HERMES_DIR/skills"
mkdir -p "$HERMES_DIR/mcp"
echo "  $HERMES_DIR prepared."

# Step 6: Configure Persona
echo ""
echo "-> Step 6: Configuring Persona..."

if [ -f "$APP_DIR/persona_soul.md" ]; then
    cp "$APP_DIR/persona_soul.md" "$HERMES_DIR/SOUL.md"
    echo "  SOUL.md synchronized."
fi

# Step 6b: Generate ~/.hermes/config.yaml
echo ""
echo "-> Step 6b: Generating Hermes configuration..."

if [ ! -f "$APP_DIR/.env" ]; then
    echo "  Warning: .env missing. Skipping config.yaml generation (handled in Step 8)."
else
    set -o allexport
    source "$APP_DIR/.env"
    set +o allexport

    cat > "$HERMES_DIR/config.yaml" << HEREDOC
model: gemini:gemini-1.5-flash

platforms:
  telegram:
    token: "${TELEGRAM_BOT_TOKEN}"

skills_dir: '${HERMES_DIR}/skills'
soul_file: '${HERMES_DIR}/SOUL.md'

platform_toolsets:
  telegram:
    - terminal
    - file
    - skills
    - web
    - memory
    - todo
HEREDOC
    echo "  config.yaml generated."
fi

# Step 6c: Generate ~/.hermes/.env (for pairing mode)
echo ""
echo "-> Step 6c: Configuring Hermes environment..."

if [ -f "$APP_DIR/.env" ]; then
    set -o allexport
    source "$APP_DIR/.env"
    set +o allexport

    if [ -n "$TELEGRAM_CHAT_ID" ]; then
        ALLOW_LINE="TELEGRAM_ALLOWED_USERS=${TELEGRAM_CHAT_ID}"
        MODE_INFO="Restricted: ${TELEGRAM_CHAT_ID}"
    else
        ALLOW_LINE="# TELEGRAM_ALLOWED_USERS="
        MODE_INFO="Open (Pairing Mode)"
    fi

    cat > "$HERMES_DIR/.env" << HEREDOC
${ALLOW_LINE}
GATEWAY_ALLOW_ALL_USERS=true
HEREDOC
    echo "  ~/.hermes/.env generated ($MODE_INFO)."
fi

# Step 7: Setup alice CLI
echo ""
echo "-> Step 7: Configuring alice CLI tools..."

chmod +x "$APP_DIR/bin/alice"
chmod +x "$APP_DIR/bin/alice_tools.py"
echo "  Executable permissions set."

# Remove old skills to prevent conflicts
rm -f "$HERMES_DIR/skills/google_workspace_skills.py"
rm -f "$HERMES_DIR/skills/calendar_skills.py"
rm -f "$HERMES_DIR/skills/gmail_skills.py"
rm -f "$HERMES_DIR/skills/tasks_skills.py"
rm -f "$HERMES_DIR/skills/drive_skills.py"
rm -f "$HERMES_DIR/skills/contacts_skills.py"
rm -f "$HERMES_DIR/skills/generation_skills.py"
rm -f "$HERMES_DIR/skills/memory_skills.py"
rm -f "$HERMES_DIR/skills/_skill_base.py"
echo "  Old skills cleaned up."

# Step 7b: Linking ai-secretary to hermes venv
echo ""
echo "-> Step 7b: Linking ai-secretary to hermes venv..."

HERMES_PYTHON="$HERMES_DIR/hermes-agent/venv/bin/python3"
if [ -f "$HERMES_PYTHON" ]; then
    "$HERMES_PYTHON" -m pip install --quiet -e "$APP_DIR"
    echo "  Success: ai-secretary linked."
else
    echo "  Warning: hermes venv ($HERMES_PYTHON) not found. Skipping link."
fi

# Step 8: Validate Environment
echo ""
echo "-> Step 8: Validating environment variables..."

if [ ! -f "$APP_DIR/.env" ]; then
    echo "  Error: .env file not found."
    exit 1
fi

set -o allexport
source "$APP_DIR/.env"
set +o allexport

MISSING=""
[ -z "$TELEGRAM_BOT_TOKEN" ] && MISSING="$MISSING TELEGRAM_BOT_TOKEN"
[ -z "$TELEGRAM_CHAT_ID" ] && MISSING="$MISSING TELEGRAM_CHAT_ID"
[ -z "$GEMINI_API_KEY" ] && MISSING="$MISSING GEMINI_API_KEY"

if [ -n "$MISSING" ]; then
    echo "  Missing variables: $MISSING"
    exit 1
fi
echo "  Environment variables validated."

# Step 9: Check Token
echo ""
echo "-> Step 9: Checking Google OAuth Token..."

if [ ! -f "$APP_DIR/token.json" ]; then
    echo "  Warning: token.json missing. Google Workspace features will require OAuth pairing."
else
    echo "  token.json found."
fi

# Step 10: Setup Systemd Service
echo ""
echo "-> Step 10: Configuring systemd service..."

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

# Ensure environment
ExecStartPre=/bin/mkdir -p $HERMES_DIR
Environment=GOOGLE_API_KEY=${GEMINI_API_KEY}
Environment=HERMES_MODEL=gemini:gemini-1.5-flash
Environment=PATH=/home/$USER/ai-secretary/bin:/home/$USER/.hermes/hermes-agent/venv/bin:/home/$USER/.local/bin:/usr/local/bin:/usr/bin:/bin
Environment=PYTHONPATH=$APP_DIR

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable ai-secretary
echo "  systemd service configured and enabled."

echo ""
echo "=========================================="
echo "  Deployment Complete!"
echo "=========================================="
echo ""
echo "  Next steps:"
echo "  - Start service: sudo systemctl start ai-secretary"
echo "  - Check logs:    journalctl -u ai-secretary -f"
echo ""
