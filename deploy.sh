#!/bin/bash
# =====================================================
# AI Secretary - Cloud Run 部署腳本
# 在 Cloud Shell 中執行：bash deploy.sh
# =====================================================

set -e

PROJECT_ID="gen-lang-client-0741928971"
REGION="asia-east1"
SERVICE_NAME="ai-secretary"
IMAGE="gcr.io/${PROJECT_ID}/${SERVICE_NAME}"

echo "🚀 開始部署 AI Secretary..."

# 1. 拉取最新程式碼
echo "📥 Step 1: 拉取最新程式碼..."
cd ~/ai-secretary
git pull origin master

# 2. 建置 Docker image
echo "🔨 Step 2: 建置 Docker image..."
gcloud builds submit --tag ${IMAGE} --project ${PROJECT_ID}

# 3. 產生 env-vars YAML（用 --env-vars-file 避免 JSON 跳脫問題）
echo "🔑 Step 3: 準備環境變數..."
ENV_FILE=$(mktemp /tmp/env_vars_XXXXXX.yaml)

# 從 .env 讀取（排除 DEBUG/PORT/空行/註解）
while IFS='=' read -r key value; do
    [[ -z "$key" || "$key" =~ ^# || "$key" == "DEBUG" || "$key" == "PORT" ]] && continue
    key=$(echo "$key" | xargs)
    value=$(echo "$value" | xargs)
    echo "$key: '$value'" >> "$ENV_FILE"
done < .env

# 加入 token.json（如果存在）
if [ -f "token.json" ]; then
    TOKEN_JSON=$(cat token.json | tr -d '\n\r')
    echo "GOOGLE_TOKEN_JSON: '${TOKEN_JSON}'" >> "$ENV_FILE"
fi

# 加入 credentials.json（如果存在）
if [ -f "credentials.json" ]; then
    CRED_JSON=$(cat credentials.json | tr -d '\n\r')
    echo "GOOGLE_CREDENTIALS_JSON: '${CRED_JSON}'" >> "$ENV_FILE"
fi

echo "  環境變數數量: $(wc -l < "$ENV_FILE")"

# 4. 部署
echo "📦 Step 4: 部署到 Cloud Run..."
gcloud run deploy ${SERVICE_NAME} \
    --image ${IMAGE} \
    --region ${REGION} \
    --allow-unauthenticated \
    --env-vars-file "$ENV_FILE" \
    --project ${PROJECT_ID}

# 清理
rm -f "$ENV_FILE"

echo ""
echo "🎉 部署完成！"
echo "📌 Service URL: https://${SERVICE_NAME}-100699333140.${REGION}.run.app"
