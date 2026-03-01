"""
結構化長期記憶服務

Google Sheets 欄位結構：
A: 時間戳 | B: 分類 | C: 事實 | D: 關鍵實體（逗號分隔）

Pinecone 整合：
- 儲存時雙寫（Sheets 備份 + Pinecone 向量索引）
- 檢索時優先使用 Pinecone 語意搜尋
"""
import datetime
import logging
from config import Config

logger = logging.getLogger(__name__)


class MemoryService:
    def __init__(self, sheets_service, llm_service=None, pinecone_memory=None):
        self.service = sheets_service
        self.llm = llm_service
        self.pinecone = pinecone_memory
        self.spreadsheet_id = Config.GOOGLE_SHEET_ID
        self.range_name = None

    def set_llm(self, llm_service):
        """延遲設定 LLM 服務（避免循環依賴）"""
        self.llm = llm_service

    def set_pinecone(self, pinecone_memory):
        """延遲設定 Pinecone 服務"""
        self.pinecone = pinecone_memory

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
            # 衝突偵測：優先用 Pinecone 語意搜尋找相似記憶
            if self.llm:
                logger.info(f"🔍 開始衝突偵測: {fact}")
                conflict_result = self._check_and_resolve_conflict(
                    fact, category, entities
                )
                logger.info(f"🔍 衝突偵測結果: {conflict_result}")
                if conflict_result == "duplicate":
                    logger.info(f"⏭️ 跳過重複記憶: {fact}")
                    return "duplicate"
                elif conflict_result == "updated":
                    logger.info(f"🔄 已更新既有記憶: {fact}")
                    return "updated"
            else:
                logger.warning("⚠️ LLM 未設定，跳過衝突偵測")

            # 新增記憶
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            memory_id = f"mem_{timestamp.replace(' ', '_').replace(':', '')}"

            # 1) 寫入 Google Sheets（備份）
            values = [[timestamp, category, fact, entities_str]]
            body = {'values': values}
            self.service.spreadsheets().values().append(
                spreadsheetId=self.spreadsheet_id,
                range=f"{self.range_name}!A:D",
                valueInputOption='RAW',
                body=body
            ).execute()

            # 2) 寫入 Pinecone（向量索引）
            if self.pinecone and self.pinecone.enabled:
                self.pinecone.upsert_memory(
                    memory_id=memory_id,
                    fact=fact,
                    category=category,
                    entities=entities,
                    timestamp=timestamp
                )

            logger.info(f"✅ 存入記憶 [{category}]: {fact}")
            return "new"

        except Exception as e:
            logger.error(f"❌ 存入記憶失敗: {str(e)}")
            return "error"

    def _check_and_resolve_conflict(self, new_fact: str, category: str,
                                     entities: list = None):
        """
        檢查並處理記憶衝突。
        優先用 Pinecone 語意搜尋找相似記憶，退化用全量比對。
        
        Returns:
            "new" - 無衝突，需要新增
            "duplicate" - 重複，不需操作
            "updated" - 已更新舊記錄
        """
        try:
            # 策略：有 Pinecone → 語意搜尋 TOP 5 再給 LLM 判斷
            #       無 Pinecone → 退化為全量 Sheets 比對
            existing_facts = []
            pinecone_hits = []

            if self.pinecone and self.pinecone.enabled:
                # Pinecone 語意搜尋（找最相似的 5 筆）
                pinecone_hits = self.pinecone.search_memories(new_fact, top_k=5)
                existing_facts = [h["fact"] for h in pinecone_hits if h["fact"]]
                logger.info(f"🔍 Pinecone 找到 {len(existing_facts)} 筆相似記憶")
            else:
                # 退化：全量 Sheets 比對
                all_rows = self._get_all_rows()
                logger.info(f"📊 現有記憶共 {len(all_rows)} 筆")
                if not all_rows:
                    return "new"
                existing_facts = [row["fact"] for row in all_rows]

            if not existing_facts:
                return "new"

            logger.info(f"📋 比對記憶: {existing_facts}")

            # 用 LLM 判斷衝突
            conflict = self.llm.check_memory_conflict(new_fact, existing_facts)
            logger.info(f"🤖 LLM 衝突判斷回傳: {conflict}")

            has_conflict = conflict.get("has_conflict", False)
            if not has_conflict:
                logger.info("✅ 無衝突，直接新增")
                return "new"

            # 有衝突 → 判斷是重複還是更新
            is_duplicate = conflict.get("is_duplicate", False)
            conflict_idx = conflict.get("conflict_index")
            reason = conflict.get("reason", "")

            if is_duplicate:
                logger.info(f"⏭️ 判定為重複: {reason}")
                return "duplicate"

            # 嘗試更新舊記錄
            if conflict_idx is not None and 0 <= conflict_idx < len(existing_facts):
                timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                entities_str = ", ".join(entities) if entities else ""
                memory_id = f"mem_{timestamp.replace(' ', '_').replace(':', '')}"

                # 更新 Sheets
                if self.pinecone and self.pinecone.enabled and pinecone_hits:
                    # 用 Pinecone 模式：先找到舊記憶的 Sheets 列再更新
                    old_fact = existing_facts[conflict_idx]
                    all_rows = self._get_all_rows()
                    matched_row = None
                    for row in all_rows:
                        if row["fact"] == old_fact:
                            matched_row = row
                            break

                    if matched_row:
                        row_number = matched_row["row_number"]
                        self.service.spreadsheets().values().update(
                            spreadsheetId=self.spreadsheet_id,
                            range=f"{self.range_name}!A{row_number}:D{row_number}",
                            valueInputOption='RAW',
                            body={'values': [[timestamp, category, new_fact, entities_str]]}
                        ).execute()
                        logger.info(
                            f"🔄 Sheets 記憶更新：'{old_fact}' → '{new_fact}' (row {row_number})"
                        )

                    # 更新 Pinecone（刪除舊的 + 寫入新的）
                    old_hit = pinecone_hits[conflict_idx]
                    self.pinecone.delete_memory(old_hit["id"])
                    self.pinecone.upsert_memory(
                        memory_id=memory_id,
                        fact=new_fact,
                        category=category,
                        entities=entities,
                        timestamp=timestamp
                    )
                    logger.info(f"🔄 Pinecone 記憶更新完成")
                else:
                    # 退化：純 Sheets 更新
                    all_rows = self._get_all_rows()
                    if conflict_idx < len(all_rows):
                        old_row = all_rows[conflict_idx]
                        row_number = old_row["row_number"]
                        self.service.spreadsheets().values().update(
                            spreadsheetId=self.spreadsheet_id,
                            range=f"{self.range_name}!A{row_number}:D{row_number}",
                            valueInputOption='RAW',
                            body={'values': [[timestamp, category, new_fact, entities_str]]}
                        ).execute()
                        logger.info(
                            f"🔄 記憶衝突解決：'{old_row['fact']}' → '{new_fact}' (row {row_number})"
                        )

                return "updated"
            else:
                logger.warning(f"⚠️ conflict_index 無效: {conflict_idx}，判定為重複跳過")
                return "duplicate"

        except Exception as e:
            logger.error(f"⚠️ 衝突偵測失敗，直接新增: {e}", exc_info=True)
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
        優先使用 Pinecone 語意搜尋，退化為關鍵字匹配。
        """
        # 優先使用 Pinecone 語意搜尋
        if self.pinecone and self.pinecone.enabled:
            return self._fetch_via_pinecone(query)

        # 退化：原本的關鍵字匹配
        return self._fetch_via_keywords(query)

    def _fetch_via_pinecone(self, query: str) -> str:
        """
        Pinecone 語意搜尋：找出最相關的 TOP 5 記憶。
        同時附帶 Sheets 的分類摘要作為補充。
        """
        try:
            hits = self.pinecone.search_memories(query, top_k=5)

            if not hits:
                # Pinecone 沒結果，退化到 Sheets
                logger.info("🔄 Pinecone 無結果，退化至 Sheets 全量搜尋")
                return self._fetch_via_keywords(query)

            result = ["【🎯 語意搜尋最相關的記憶】"]
            for h in hits:
                score_pct = f"{h['score']:.0%}" if h.get('score') else ""
                result.append(
                    f"  - [{h['category']}] {h['fact']} ({score_pct})"
                )

            # 附帶其他分類的摘要
            if self._ensure_range_name():
                all_rows = self._get_all_rows()
                hit_facts = {h['fact'] for h in hits}
                other = [r for r in all_rows if r['fact'] not in hit_facts]
                if other:
                    cat_summary = {}
                    for r in other:
                        cat = r["category"]
                        cat_summary[cat] = cat_summary.get(cat, 0) + 1
                    result.append("\n【📁 其他記憶摘要】")
                    for cat, count in cat_summary.items():
                        result.append(f"  - {cat}: {count} 筆")

            return "\n".join(result)

        except Exception as e:
            logger.error(f"❌ Pinecone 檢索失敗，退化至關鍵字: {e}")
            return self._fetch_via_keywords(query)

    def _fetch_via_keywords(self, query: str) -> str:
        """關鍵字匹配（退化模式）"""
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

        # 組合結果
        result = []
        if relevant:
            result.append("【🎯 與問題最相關的記憶】")
            for r in relevant:
                result.append(f"  - [{r['category']}] {r['fact']}")

        if other:
            cat_summary = {}
            for r in other:
                cat = r["category"]
                cat_summary[cat] = cat_summary.get(cat, 0) + 1
            result.append("\n【📁 其他記憶摘要】")
            for cat, count in cat_summary.items():
                result.append(f"  - {cat}: {count} 筆")

        return "\n".join(result) if result else "目前沒有相關記憶。"
