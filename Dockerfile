# 使用 Python 3.12 輕量版
FROM python:3.12-slim

# 設定工作目錄
WORKDIR /app

# 安裝系統依賴 (如果需要的話)
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# 複製依賴清單並安裝
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 複製專案原始碼
COPY . .

# 暴露埠號 (Cloud Run 預設會使用 8080)
EXPOSE 8080

# 啟動應用程式
# 使用 shell 形式以確保 $PORT 變數能被正確替換
CMD uvicorn app:app --host 0.0.0.0 --port ${PORT:-8080}
