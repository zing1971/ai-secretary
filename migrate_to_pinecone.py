"""
既有記憶遷移腳本：Google Sheets → Pinecone

將 Google Sheets 中的所有結構化記憶批次寫入 Pinecone 向量資料庫。
這是一次性執行的遷移工具。

用法：
    python migrate_to_pinecone.py
"""
import os
import sys
import logging

# 設定 logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# 載入 .env
from dotenv import load_dotenv
load_dotenv()

from config import Config
from google_auth import get_google_services
from pinecone_memory import PineconeMemory


def main():
    """執行遷移"""
    logger.info("🚀 開始將 Google Sheets 記憶遷移到 Pinecone...")

    # 驗證環境
    if not Config.validate():
        logger.error("❌ 環境變數驗證失敗")
        sys.exit(1)

    if not Config.PINECONE_API_KEY:
        logger.error("❌ 請設定 PINECONE_API_KEY")
        sys.exit(1)

    # 初始化服務
    _, _, _, sheets = get_google_services()
    if not sheets:
        logger.error("❌ 無法初始化 Google Sheets 服務")
        sys.exit(1)

    pinecone = PineconeMemory()
    if not pinecone.enabled:
        logger.error("❌ Pinecone 初始化失敗")
        sys.exit(1)

    # 讀取 Sheets 記憶
    try:
        spreadsheet = sheets.spreadsheets().get(
            spreadsheetId=Config.GOOGLE_SHEET_ID
        ).execute()
        sheet_title = spreadsheet['sheets'][0]['properties']['title']
        range_name = f"'{sheet_title}'!A:D"

        result = sheets.spreadsheets().values().get(
            spreadsheetId=Config.GOOGLE_SHEET_ID,
            range=range_name
        ).execute()
        rows = result.get('values', [])
    except Exception as e:
        logger.error(f"❌ 讀取 Sheets 失敗: {e}")
        sys.exit(1)

    if not rows:
        logger.info("📭 Sheets 中沒有記憶，無需遷移")
        return

    logger.info(f"📊 Sheets 共有 {len(rows)} 筆記憶")

    # 逐筆遷移
    success = 0
    failed = 0

    for i, row in enumerate(rows):
        try:
            # 解析欄位（支援新舊格式）
            if len(row) >= 3:
                # 新格式：A:時間 B:分類 C:事實 D:實體
                timestamp = row[0]
                category = row[1]
                fact = row[2]
                entities_str = row[3] if len(row) > 3 else ""
            elif len(row) >= 2:
                # 舊格式：A:時間 B:事實
                timestamp = row[0]
                category = "其他"
                fact = row[1]
                entities_str = ""
            else:
                logger.warning(f"⏭️ 跳過第 {i+1} 列（格式不符）: {row}")
                continue

            if not fact.strip():
                continue

            # 產生唯一 ID
            ts_clean = timestamp.replace(" ", "_").replace(":", "").replace("-", "")
            memory_id = f"mem_{ts_clean}_{i}"

            # 解析實體
            entities = [e.strip() for e in entities_str.split(",") if e.strip()] if entities_str else []

            # 寫入 Pinecone
            ok = pinecone.upsert_memory(
                memory_id=memory_id,
                fact=fact,
                category=category,
                entities=entities,
                timestamp=timestamp
            )

            if ok:
                success += 1
                logger.info(f"  ✅ [{i+1}/{len(rows)}] {fact[:40]}...")
            else:
                failed += 1
                logger.warning(f"  ❌ [{i+1}/{len(rows)}] 寫入失敗: {fact[:40]}...")

        except Exception as e:
            failed += 1
            logger.error(f"  ❌ [{i+1}/{len(rows)}] 例外: {e}")

    # 完成報告
    logger.info(f"\n{'='*50}")
    logger.info(f"🏁 遷移完成！")
    logger.info(f"   ✅ 成功: {success} 筆")
    logger.info(f"   ❌ 失敗: {failed} 筆")
    logger.info(f"{'='*50}")


if __name__ == "__main__":
    main()
