#!/bin/bash
set -e

# --- Configuration ---
APP_DIR="/home/$USER/ai-secretary"
HERMES_DIR="/home/$USER/.hermes"
VENV_PATH="$APP_DIR/venv"

echo "🚀 Starting Simplified Deployment..."

# 1. System Dependencies
echo "📦 Installing system dependencies..."
sudo apt-get update -y
sudo apt-get install -y python3-venv python3-pip ffmpeg libmagic-dev git

# 2. Venv Setup
echo "🐍 Setting up Python virtual environment..."
if [ ! -d "$VENV_PATH" ]; then
    python3 -m venv "$VENV_PATH"
fi
"$VENV_PATH/bin/pip" install --upgrade pip
"$VENV_PATH/bin/pip" install -r "$APP_DIR/requirements.txt"

# 3. Hermes Agent
echo "🕊️ Installing Hermes Agent..."
if [ ! -d "$HERMES_DIR/hermes-agent" ]; then
    mkdir -p "$HERMES_DIR"
    cd "$HERMES_DIR"
    git clone https://github.com/zing1971/hermes-agent.git
fi
cd "$HERMES_DIR/hermes-agent"
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi
./venv/bin/pip install -e .

# 4. SOUL.md & Directory
echo "🧠 Setting up Persona & Config..."
mkdir -p "$HERMES_DIR"
cp "$APP_DIR/persona_soul.md" "$HERMES_DIR/SOUL.md"

# 5. Systemd Service
echo "⚙️ Configuring systemd service..."
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
ExecStart=$VENV_PATH/bin/python $APP_DIR/main.py
Restart=always
RestartSec=10
Environment=PATH=$APP_DIR/bin:$HERMES_DIR/hermes-agent/venv/bin:/usr/local/bin:/usr/bin:/bin
Environment=PYTHONPATH=$APP_DIR

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable ai-secretary
sudo systemctl restart ai-secretary

echo "✅ Deployment Successful!"
echo "Check logs with: journalctl -u ai-secretary -f"
