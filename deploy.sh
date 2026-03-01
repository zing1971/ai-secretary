#!/bin/bash
# =====================================================
# AI Secretary - Cloud Run 部署腳本 (含 Drive scope)
# 在 Cloud Shell 中執行此腳本
# =====================================================

set -e

PROJECT_ID="gen-lang-client-0741928971"
REGION="asia-east1"
SERVICE_NAME="ai-secretary"
IMAGE="gcr.io/${PROJECT_ID}/${SERVICE_NAME}"

echo "🚀 開始部署 AI Secretary (含 Drive 整理功能)..."

# 1. 拉取最新程式碼
echo "📥 Step 1: 拉取最新程式碼..."
cd ~/ai-secretary
git pull origin master

# 2. 建置 Docker image
echo "🔨 Step 2: 建置 Docker image..."
gcloud builds submit --tag ${IMAGE} --project ${PROJECT_ID}

# 3. 更新 GOOGLE_TOKEN_JSON（從本機 token.json 讀取）
# 需要先手動將新的 token.json 上傳到 Cloud Shell
echo "🔑 Step 3: 請確保 token.json 已更新（含 Drive scope）"
echo "   如果需要更新，請將新的 token.json 上傳到 ~/ai-secretary/ 目錄"

# 4. 讀取 token 並部署
if [ -f "token.json" ]; then
    TOKEN_JSON=$(cat token.json | tr -d '\n')
    echo "📦 Step 4: 部署到 Cloud Run..."
    gcloud run deploy ${SERVICE_NAME} \
        --image ${IMAGE} \
        --region ${REGION} \
        --allow-unauthenticated \
        --update-env-vars "GOOGLE_TOKEN_JSON=${TOKEN_JSON}" \
        --project ${PROJECT_ID}
    echo "✅ 部署完成！（含新 Token）"
else
    echo "⚠️ 未找到 token.json，部署不更新 Token..."
    gcloud run deploy ${SERVICE_NAME} \
        --image ${IMAGE} \
        --region ${REGION} \
        --allow-unauthenticated \
        --project ${PROJECT_ID}
    echo "✅ 部署完成！（Token 未更新）"
fi

echo ""
echo "🎉 部署結束！"
echo "📌 請記得在 Cloud Shell 上手動更新 token.json（如尚未更新）"
echo "   可使用: gcloud run services update ${SERVICE_NAME} --region ${REGION} --update-env-vars 'GOOGLE_TOKEN_JSON=<token_json_content>'"
