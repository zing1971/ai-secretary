#!/bin/bash
set -e

echo "🚀 初始化 AI Secretary (Hermes Agent 架構)..."

# 確保 Hermes 設定目錄與技能目錄存在
mkdir -p ~/.hermes/skills
mkdir -p ~/.hermes/mcp

echo "📌 設定 Persona (靈魂)..."
if [ -f "persona_soul.md" ]; then
    cp persona_soul.md ~/.hermes/SOUL.md
else
    echo "⚠️ 找不到 persona_soul.md"
fi

# 將現有設定載入為環境變數 (處理 .env)
if [ -f ".env" ]; then
    export $(grep -v '^#' .env | xargs)
fi

echo "⚙️ 檢查必填環境變數..."
if [ -z "$TELEGRAM_BOT_TOKEN" ]; then
    echo "❌ 缺少 TELEGRAM_BOT_TOKEN"
    exit 1
fi

if [ -z "$GEMINI_API_KEY" ]; then
    echo "❌ 缺少 GEMINI_API_KEY"
    exit 1
fi

echo "🌐 啟動 Hermes Gateway..."
export HERMES_MODEL="gemini-1.5-flash"  # 使用 Google 原生 Gemini 1.5 Flash 模型

# 將當前專案目錄加入 PYTHONPATH，這樣 google_workspace_skills.py 就能正確 import 其他檔案
export PYTHONPATH="$PWD:$PYTHONPATH"

# 將封裝好的技能複製到 Hermes 技能目錄
cp google_workspace_skills.py ~/.hermes/skills/

exec hermes gateway start
