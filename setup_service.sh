#!/bin/bash
set -e
APP_DIR="/home/zing/ai-secretary"
VENV_PATH="$APP_DIR/venv"

echo "⚙️ Configuring systemd service..."
sudo tee /etc/systemd/system/ai-secretary.service > /dev/null << EOF
[Unit]
Description=AI Secretary (Hermes Agent)
After=network.target

[Service]
Type=simple
User=zing
WorkingDirectory=$APP_DIR
EnvironmentFile=$APP_DIR/.env
ExecStart=$VENV_PATH/bin/python $APP_DIR/main.py
Restart=always
RestartSec=10
Environment=PATH=$APP_DIR/bin:$VENV_PATH/bin:/usr/local/bin:/usr/bin:/bin
Environment=PYTHONPATH=$APP_DIR

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable ai-secretary
sudo systemctl restart ai-secretary
sleep 3
sudo systemctl status ai-secretary --no-pager
