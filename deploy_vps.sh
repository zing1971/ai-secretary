#!/bin/bash
# =====================================================
# AI Secretary (Hermes Agent) - VPS ?函蔡?單
# ?冽?嚗 VPS 銝銵?bash deploy_vps.sh
# =====================================================
set -e

APP_DIR="$HOME/ai-secretary"
HERMES_DIR="$HOME/.hermes"
REPO_URL="https://github.com/zing1971/ai-secretary.git"

echo "=========================================="
echo "  AI Secretary - Hermes Agent ?函蔡?單"
echo "=========================================="

# ?? Step 1: 蝟餌絞?啣?皞? ??????????????????????????????????
echo ""
echo "? Step 1: 瑼Ｘ蝟餌絞靘陷..."

# 蝣箔? Python 3.11+ ?舐
if ! command -v python3 &> /dev/null; then
    echo "???曆???python3嚗迤?典?鋆?.."
    sudo apt-get update && sudo apt-get install -y python3 python3-pip python3-venv
fi

PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo "  Python ?: $PYTHON_VERSION"

# 蝣箔? git ?舐
if ! command -v git &> /dev/null; then
    sudo apt-get install -y git
fi

# ?? Step 2: ??蝔?蝣?????????????????????????????????????
echo ""
echo "? Step 2: 閮剖?蝔?蝣?.."

if [ -d "$APP_DIR/.git" ]; then
    echo "  撌脫? repo嚗????啁???.."
    cd "$APP_DIR"
  # git pull skipped
else
    echo "  擐活?函蔡嚗? GitHub ??..."
    git clone "$REPO_URL" "$APP_DIR"
    cd "$APP_DIR"
fi

# ?? Step 3: Python ??啣? ???????????????????????????????
echo ""
echo "?? Step 3: 閮剖? Python ??啣?..."

if [ ! -d "$APP_DIR/venv" ]; then
    python3 -m venv "$APP_DIR/venv"
    echo "  ??啣?撌脣遣蝡?
fi

source "$APP_DIR/venv/bin/activate"
pip install --upgrade pip -q
pip install -r requirements.txt -q
echo "  靘陷摰?摰???

# ?? Step 4: 蝣箄? hermes-agent 撌脤? pip 摰? ????????????????
echo ""
echo "?? Step 4: 蝣箄? hermes-agent..."

if ! "$APP_DIR/venv/bin/hermes" --version &> /dev/null; then
    echo "  摰? hermes-agent ??venv..."
    "$APP_DIR/venv/bin/pip" install hermes-agent -q
fi
echo "  hermes-agent 撌脣停蝺?

# ?? Step 5: 撱箇???????????????????????????????????????
echo ""
echo "? Step 5: 蝣箔????????.."

mkdir -p "$HERMES_DIR/skills"
mkdir -p "$HERMES_DIR/mcp"
echo "  $HERMES_DIR 撌脣停蝺?

# ?? Step 6: 閮剖? Persona ??????????????????????????????????
echo ""
echo "????Step 6: ?函蔡 Persona 閮剖?..."

if [ -f "$APP_DIR/persona_soul.md" ]; then
    cp "$APP_DIR/persona_soul.md" "$HERMES_DIR/SOUL.md"
    echo "  SOUL.md 撌脣?甇乓?
fi

# ?? Step 6b: ?? ~/.hermes/config.yaml ??????????????????
echo ""
echo "??  Step 6b: ?? Hermes 閮剖?瑼?.."

if [ ! -f "$APP_DIR/.env" ]; then
    echo "  ?? ?曆???.env嚗歲??config.yaml ??嚗???Step 8 銝剜迫嚗?
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

# ??telegram 撟喳?Ⅱ??閬? toolsets
platform_toolsets:
  telegram:
    - terminal
    - file
    - skills
    - web
    - memory
    - todo
HEREDOC
# 瘜冽?嚗?? vision toolset嚗??hermes 撠?vision_analyze ?撌亙?”嚗?
# 霈?Gemini 憭芋???亥?????vision_analyze ?閬?OpenRouter嚗??冽迨雿輻嚗?

    echo "  config.yaml 撌脩???terminal toolset 撌脣??剁???
fi

# ?€?€ Step 6c: ?? ~/.hermes/.env嚗?嗥?嚗??€?€?€?€?€?€?€?€?€?€?€?€?€?€?€
echo ""
echo "??  Step 6c: ?? Hermes ?冽?賢??株身摰?.."

if [ -f "$APP_DIR/.env" ]; then
    set -o allexport
    source "$APP_DIR/.env"
    set +o allexport

    # 判定是否處於配對模式（未設定 Chat ID 時）
    if [ -n "$TELEGRAM_CHAT_ID" ]; then
        ALLOW_LINE="TELEGRAM_ALLOWED_USERS=${TELEGRAM_CHAT_ID}"
        MODE_INFO="受限模式: ${TELEGRAM_CHAT_ID}"
    else
        ALLOW_LINE="# TELEGRAM_ALLOWED_USERS=（未配對模式，允許所有人發送指令以查詢 ID）"
        MODE_INFO="未配對模式（開放）"
    fi

    cat > "$HERMES_DIR/.env" << HEREDOC
${ALLOW_LINE}
GATEWAY_ALLOW_ALL_USERS=true
HEREDOC
    echo "  ~/.hermes/.env 建立完成（目前模式：$MODE_INFO）"
else
    echo "  ⚠️  找不到 .env 檔案，跳過 ~/.hermes/.env 設定。"
fi

# ?€?€ Step 7: ?函蔡 alice CLI 撌亙 ?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€
echo ""
echo "? Step 7: ?函蔡 alice CLI 撌亙..."

# 蝣箔? bin/ ?桅?摮銝行??瑁?甈?
chmod +x "$APP_DIR/bin/alice"
chmod +x "$APP_DIR/bin/alice_tools.py"
echo "  bin/alice ??bin/alice_tools.py 撌脰身摰銵???

# 蝘駁???像撘??賣?獢????箇?嚗歇銝蝙?剁?
rm -f "$HERMES_DIR/skills/google_workspace_skills.py"
rm -f "$HERMES_DIR/skills/calendar_skills.py"
rm -f "$HERMES_DIR/skills/gmail_skills.py"
rm -f "$HERMES_DIR/skills/tasks_skills.py"
rm -f "$HERMES_DIR/skills/drive_skills.py"
rm -f "$HERMES_DIR/skills/contacts_skills.py"
rm -f "$HERMES_DIR/skills/generation_skills.py"
rm -f "$HERMES_DIR/skills/memory_skills.py"
rm -f "$HERMES_DIR/skills/_skill_base.py"
echo "  ???像撘??賣?獢歇皜??

# 撱箇? ai-secretary skill 憟辣嚗ermes ??SKILL.md 霅嚗?
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

Alice ?? `terminal` 撌亙?瑁? `alice` ?賭誘靘?雿?Google Workspace??

## ?賭誘?韌

```bash
# alice ?賭誘撌脣???PATH嚗?湔?澆
alice <domain> <action> [--arg value ...]
```

## 銵???Calendar嚗?

```bash
alice calendar list
alice calendar create --title "?望?" --start "2026-04-20 10:00" --end "2026-04-20 11:00"
alice calendar create --title "?望?" --start "2026-04-20 10:00" --end "2026-04-20 11:00" --location "?降摰?A" --desc "?酉"
alice calendar create --title "隡?" --start "2026-04-25" --end "2026-04-26"
```

## 靽∩辣嚗mail嚗?

```bash
alice gmail search
alice gmail search --query "is:unread" --max 10
alice gmail draft --to "user@example.com" --subject "銝餅" --body "?扳?嚗?銵 \n嚗?
```

## 敺齒鈭?嚗asks嚗?

```bash
alice tasks list
alice tasks add --title "隞餃?璅?"
alice tasks add --title "隞餃?璅?" --notes "?酉" --due "2026-05-01T23:59:59Z"
```

## ?脩垢蝖祉?嚗rive嚗?

```bash
alice drive search --keyword "?摮? --max 5
```

## ?舐窗鈭綽?Contacts嚗?

```bash
alice contacts search --query "憪????
alice contacts create --name "憪?" --email "email@example.com" --phone "??" --company "?砍" --title "?瑞迂" --label "撱?隞?”"
```

?舐璅惜嚗摨??飛銵?蝛嗚??誨銵具??萄丰隡氬?擃?隞?

## 韏瑁?撠平?批捆嚗enerate嚗?

雿輻 Gemini 2.5 Pro ??擃?鞈芣迤撘摰嫘?

```bash
alice generate --task "隞餃??膩"
alice generate --task "韏瑁???靽∠策?之?鈭" --context "銝勗??隢?撘鈭?雿?閬犖憯?
```

## ?瑟?閮嚗emory嚗?

```bash
alice memory remember --topic "銝駁?" --content "?批捆"
alice memory recall
alice memory recall --query "?摮?
alice memory forget --topic "銝駁?"
```
SKILL_EOF

echo "  ~/.hermes/skills/ai-secretary/SKILL.md 撌脣遣蝡?

# 撠?ai-secretary 隞?editable 璅∪?摰???hermes ??venv嚗?
# 霈?alice_tools.py ?臭誑 import google_auth / gmail_service 蝑??芋蝯?
HERMES_PYTHON="$HERMES_DIR/hermes-agent/venv/bin/python3"
if [ -f "$HERMES_PYTHON" ]; then
    echo "  隞?pip install -e 撠?ai-secretary 摰???hermes venv..."
    "$HERMES_PYTHON" -m pip install --quiet -e "$APP_DIR"
    echo "  ??ai-secretary 憟辣摰?摰?嚗ditable 璅∪?嚗?
else
    echo "  ?? ?曆???hermes venv ($HERMES_PYTHON)嚗歲??隞嗅?鋆?
fi

# ?? Step 8: ?啣?霈瑼Ｘ ??????????????????????????????????
echo ""
echo "?? Step 8: 瑼Ｘ?啣?霈..."

if [ ! -f "$APP_DIR/.env" ]; then
    echo "  ?? ?曆???.env 瑼?嚗?
    echo "  隢? .env.example 銴ˊ銝血‵?交迤蝣箇??潘?"
    echo "    cp .env.example .env"
    echo "    nano .env"
    echo ""
    echo "  ?函蔡?單??銝剜迫嚗? .env 閮剖?摰?敺?甈∪銵?
    exit 1
fi

# 頛 .env 銝血??箸撽?
set -o allexport
source "$APP_DIR/.env"
set +o allexport

MISSING=""
[ -z "$TELEGRAM_BOT_TOKEN" ] && MISSING="$MISSING TELEGRAM_BOT_TOKEN"
[ -z "$TELEGRAM_CHAT_ID" ] && MISSING="$MISSING TELEGRAM_CHAT_ID"
[ -z "$GEMINI_API_KEY" ] && MISSING="$MISSING GEMINI_API_KEY"

if [ -n "$MISSING" ]; then
    echo "  ??蝻箏?敹??啣?霈:$MISSING"
    echo "  隢楊頛?.env 敺?甈∪銵蝵脯?
    exit 1
fi

echo "  ???啣?霈撽?????

# ?? Step 9: 閮剖? token.json ???????????????????????????????
echo ""
echo "?? Step 9: 瑼Ｘ Google OAuth Token..."

if [ ! -f "$APP_DIR/token.json" ]; then
    echo "  ?? ?曆???token.json嚗?
    echo "  Google Workspace ??賢??⊥?雿輻??
    echo "  隢?砍?瑁???敺? token.json 銝??$APP_DIR/"
    echo "  (scp token.json user@vps:~/ai-secretary/)"
else
    echo "  ??token.json 撌脣??具?
fi

# ?? Step 10: 撱箇? systemd ?? ?????????????????????????????
echo ""
echo "?? Step 10: 閮剖? systemd ??隞亦Ⅱ靽?璈??.."

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

# 蝣箔? Hermes ?桅?摮
ExecStartPre=/bin/mkdir -p $HERMES_DIR

# ?啣?霈
Environment=HERMES_MODEL=gemini-2.5-flash
# alice ?賭誘??hermes venv ????PATH嚗? terminal tool ?舐?亙??
Environment=PATH=/home/$USER/ai-secretary/bin:/home/$USER/.hermes/hermes-agent/venv/bin:/home/$USER/.local/bin:/usr/local/bin:/usr/bin:/bin
Environment=PYTHONPATH=$APP_DIR

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable ai-secretary
echo "  ??systemd ??撌脰身摰蒂????芸???

echo ""
echo "=========================================="
echo "  ???函蔡摰?嚗?
echo "=========================================="
echo ""
echo "  ????嚗?
echo "  ?? ????:  sudo systemctl start ai-secretary"
echo "  ?? ?迫??:  sudo systemctl stop ai-secretary"
echo "  ?? ?亦????  sudo systemctl status ai-secretary"
echo "  ?? ?亦??亥?:  journalctl -u ai-secretary -f"
  # git pull skipped
echo ""
echo "  擐活??隢銵? sudo systemctl start ai-secretary"
echo ""
