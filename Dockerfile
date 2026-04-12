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

# 暴露可能需要的埠號 (例如 MCP Server 等)
EXPOSE 8080

# 宣告 Volume 掛載點以保護 Hermes 代理程式記憶體 (SQLite + Markdown)
VOLUME ["/root/.hermes"]

# 確保啟動腳本具備執行權限
RUN chmod +x start_agent.sh

# 啟動應用程式
CMD ["./start_agent.sh"]
