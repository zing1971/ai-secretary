"""
結構化長期記憶服務

Google Sheets 欄位結構：
A: 時間戳 | B: 分類 | C: 事實 | D: 關鍵實體（逗號分隔）
"""
import datetime
import logging
from config import Config

logger = logging.getLogger(__name__)


class MemoryService:
    def __init__(self, sheets_service, llm_service=None):
        self.service = sheets_service
        self.llm = llm_service
        self.spreadsheet_id = Config.GOOGLE_SHEET_ID
        self.range_name = None

    def set_llm(self, llm_service):
        """延遲設定 LLM 服務（避免循環依賴）"""
        self.llm = llm_service

    def _ensure_range_name(self):
        """動態取得第一張工作表的名稱"""
        if self.range_name:
            return True
        try:
            spreadsheet = self.service.spreadsheets().get(
                spreadsheetId=self.spreadsheet_id
            ).execute()
            sheet_title = spreadsheet['sheets'][0]['properties']['title']
            self.range_name = f"'{sheet_title}'"
            logger.info(f"📌 偵測到記憶工作表: {self.range_name}")
            return True
        except Exception as e:
            logger.error(f"❌ 無法取得工作表資訊: {e}")
            return False

    # ===== 儲存記憶 =====

    def save_memory(self, fact_data) -> str:
        """
        儲存結構化記憶，支援衝突偵測。
        
        Args:
            fact_data: dict {"fact": str, "category": str, "entities": list}
                       或 str（向下相容舊格式）
        Returns:
            "new" - 新增成功
            "duplicate" - 重複跳過
            "updated" - 衝突更新
            "error" - 儲存失敗
        """
        if not self._ensure_range_name():
            return "error"

        # 向下相容：如果傳入純字串，包裝為 dict
        if isinstance(fact_data, str):
            fact_data = {
                "fact": fact_data,
                "category": "其他",
                "entities": []
            }

        fact = fact_data.get("fact", "")
        category = fact_data.get("category", "其他")
        entities = fact_data.get("entities", [])
        entities_str = ", ".join(entities) if entities else ""

        if not fact:
            return "error"

        try:
            # 衝突偵測：跨分類搜尋全部記憶
            if self.llm:
                conflict_result = self._check_and_resolve_conflict(
                    fact, category
                )
                if conflict_result == "duplicate":
                    logger.info(f"⏭️ 跳過重複記憶: {fact}")
                    return "duplicate"
                elif conflict_result == "updated":
                    logger.info(f"🔄 已更新既有記憶: {fact}")
                    return "updated"

            # 新增記憶
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            values = [[timestamp, category, fact, entities_str]]
            body = {'values': values}

            self.service.spreadsheets().values().append(
                spreadsheetId=self.spreadsheet_id,
                range=f"{self.range_name}!A:D",
                valueInputOption='RAW',
                body=body
            ).execute()

            logger.info(f"✅ 存入記憶 [{category}]: {fact}")
            return "new"

        except Exception as e:
            logger.error(f"❌ 存入記憶失敗: {str(e)}")
            return "error"

    def _check_and_resolve_conflict(self, new_fact: str, category: str):
        """
        檢查並處理記憶衝突（搜尋全部記憶，不限分類）。
        
        Returns:
            "new" - 無衝突，需要新增
            "duplicate" - 重複，不需操作
            "updated" - 已更新舊記錄
        """
        try:
            # 取得全部記憶（跨分類比對，避免舊資料漏掉）
            all_rows = self._get_all_rows()
            if not all_rows:
                return "new"

            existing_facts = [row["fact"] for row in all_rows]

            # 用 LLM 判斷衝突
            conflict = self.llm.check_memory_conflict(new_fact, existing_facts)

            if not conflict.get("has_conflict", False):
                return "new"

            reason = conflict.get("reason", "")
            logger.info(f"🔍 衝突偵測結果: {reason}")

            # 如果是重複
            if "重複" in reason or "相同" in reason:
                return "duplicate"

            # 如果是更新（衝突），覆蓋舊記錄
            conflict_idx = conflict.get("conflict_index")
            if conflict_idx is not None and 0 <= conflict_idx < len(all_rows):
                old_row = all_rows[conflict_idx]
                row_number = old_row["row_number"]
                timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                entities_str = ", ".join(
                    self.llm.extract_search_keywords(new_fact)
                ) if self.llm else ""

                # 覆蓋既有列（同時更新分類）
                self.service.spreadsheets().values().update(
                    spreadsheetId=self.spreadsheet_id,
                    range=f"{self.range_name}!A{row_number}:D{row_number}",
                    valueInputOption='RAW',
                    body={'values': [[timestamp, category, new_fact, entities_str]]}
                ).execute()

                logger.info(
                    f"🔄 記憶衝突解決：'{old_row['fact']}' → '{new_fact}'"
                )
                return "updated"

            return "new"


        except Exception as e:
            logger.warning(f"⚠️ 衝突偵測失敗，直接新增: {e}")
            return "new"

    # ===== 讀取記憶 =====

    def _get_all_rows(self) -> list:
        """讀取所有記憶列（含列號）"""
        try:
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range=f"{self.range_name}!A:D"
            ).execute()

            rows = result.get('values', [])
            parsed = []
            for i, row in enumerate(rows):
                if len(row) >= 3:
                    parsed.append({
                        "row_number": i + 1,
                        "timestamp": row[0] if len(row) > 0 else "",
                        "category": row[1] if len(row) > 1 else "其他",
                        "fact": row[2] if len(row) > 2 else "",
                        "entities": row[3] if len(row) > 3 else ""
                    })
                elif len(row) >= 2:
                    # 向下相容舊格式（只有 A:時間 B:事實）
                    parsed.append({
                        "row_number": i + 1,
                        "timestamp": row[0],
                        "category": "其他",
                        "fact": row[1],
                        "entities": ""
                    })
            return parsed

        except Exception as e:
            logger.error(f"❌ 讀取記憶失敗: {e}")
            return []

    def _get_memories_by_category(self, category: str) -> list:
        """取得指定分類的記憶"""
        all_rows = self._get_all_rows()
        return [r for r in all_rows if r["category"] == category]

    def fetch_all_memories(self) -> str:
        """取得所有記憶，按分類整理（向下相容）"""
        if not self._ensure_range_name():
            return "無法取得長期記憶。"

        all_rows = self._get_all_rows()
        if not all_rows:
            return "目前沒有儲存任何記憶。"

        # 按分類分組
        categories = {}
        for row in all_rows:
            cat = row["category"]
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(row["fact"])

        # 格式化輸出
        result = []
        for cat, facts in categories.items():
            result.append(f"【{cat}】")
            for f in facts:
                result.append(f"  - {f}")

        return "\n".join(result)

    def fetch_relevant_memories(self, query: str) -> str:
        """
        智慧檢索：根據問題返回最相關的記憶。
        結合關鍵字匹配 + 全量分類摘要。
        """
        if not self._ensure_range_name():
            return "無法取得長期記憶。"

        all_rows = self._get_all_rows()
        if not all_rows:
            return "目前沒有儲存任何記憶。"

        # 如果記憶量少 (≤30)，直接全量返回
        if len(all_rows) <= 30:
            return self.fetch_all_memories()

        # 用 LLM 萃取搜尋關鍵字
        keywords = []
        if self.llm:
            keywords = self.llm.extract_search_keywords(query)
            logger.info(f"🔍 搜尋關鍵字: {keywords}")

        # 關鍵字匹配
        relevant = []
        other = []
        for row in all_rows:
            searchable = (
                row["fact"] + " " + row["entities"] + " " + row["category"]
            ).lower()
            matched = any(kw.lower() in searchable for kw in keywords)
            if matched:
                relevant.append(row)
            else:
                other.append(row)

        # 組合結果：相關記憶 + 分類摘要
        result = []

        if relevant:
            result.append("【🎯 與問題最相關的記憶】")
            for r in relevant:
                result.append(f"  - [{r['category']}] {r['fact']}")

        # 提供其他分類的摘要（不佔太多 token）
        if other:
            cat_summary = {}
            for r in other:
                cat = r["category"]
                cat_summary[cat] = cat_summary.get(cat, 0) + 1

            result.append("\n【📁 其他記憶摘要】")
            for cat, count in cat_summary.items():
                result.append(f"  - {cat}: {count} 筆")

        return "\n".join(result) if result else "目前沒有相關記憶。"
