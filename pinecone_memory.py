"""
Pinecone 向量記憶服務

使用 Pinecone Integrated Inference（multilingual-e5-large 模型）
自動處理文字嵌入和語意搜尋。

索引: alice-memory
命名空間: default
文本欄位: chunk_text（對應 fieldMap text→chunk_text）
"""
import logging
import datetime
from pinecone import Pinecone
from config import Config

logger = logging.getLogger(__name__)

# alice-memory 索引的 host
INDEX_HOST = "alice-memory-5gz0rkj.svc.aped-4627-b74a.pinecone.io"


class PineconeMemory:
    """Pinecone 向量記憶管理（Integrated Inference 模式）"""

    def __init__(self):
        self.enabled = False
        self.index = None
        self.namespace = "default"
        self._init_client()

    def _init_client(self):
        """初始化 Pinecone 客戶端"""
        api_key = Config.PINECONE_API_KEY
        if not api_key:
            logger.warning("⚠️ Pinecone API Key 未設定，向量記憶服務停用")
            return

        try:
            pc = Pinecone(api_key=api_key)
            self.index = pc.Index(host=INDEX_HOST)
            self.enabled = True
            logger.info("✅ Pinecone 向量記憶服務已啟動 (index: alice-memory)")
        except Exception as e:
            logger.error(f"❌ Pinecone 初始化失敗: {e}")
            self.enabled = False

    def upsert_memory(self, memory_id: str, fact: str,
                      category: str = "其他",
                      entities: list = None,
                      timestamp: str = None) -> bool:
        """
        將記憶寫入 Pinecone（Integrated Inference 自動嵌入）。

        Args:
            memory_id: 記憶唯一 ID
            fact: 事實文字
            category: 分類
            entities: 關鍵實體列表
            timestamp: 時間戳
        """
        if not self.enabled:
            logger.warning("⚠️ Pinecone 未啟用，跳過向量寫入")
            return False

        if not timestamp:
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        entities_str = ", ".join(entities) if entities else ""

        # Integrated Inference 模式：使用 upsert_records
        # chunk_text 是 fieldMap 中映射的文本欄位，會自動嵌入
        record = {
            "_id": memory_id,
            "chunk_text": fact,
            "category": category,
            "entities": entities_str,
            "timestamp": timestamp
        }

        try:
            self.index.upsert_records(
                namespace=self.namespace,
                records=[record]
            )
            logger.info(f"✅ Pinecone 寫入成功: {memory_id} → {fact[:30]}...")
            return True
        except Exception as e:
            logger.error(f"❌ Pinecone 寫入失敗: {e}")
            return False

    def search_memories(self, query: str, top_k: int = 5,
                        category: str = None) -> list:
        """
        語意搜尋最相關的記憶（Integrated Inference 自動嵌入查詢文字）。

        Args:
            query: 搜尋文字
            top_k: 回傳數量
            category: 可選，按分類過濾

        Returns:
            list of dict: [{id, fact, category, entities, timestamp, score}]
        """
        if not self.enabled:
            logger.warning("⚠️ Pinecone 未啟用，無法進行語意搜尋")
            return []

        try:
            search_params = {
                "namespace": self.namespace,
                "query": {
                    "inputs": {"text": query},
                    "top_k": top_k
                }
            }

            # metadata 過濾
            if category:
                search_params["query"]["filter"] = {
                    "category": {"$eq": category}
                }

            results = self.index.search(**search_params)

            memories = []
            if results and hasattr(results, 'result') and results.result:
                for hit in results.result.hits:
                    fields = hit.fields or {}
                    memories.append({
                        "id": hit._id,
                        "fact": fields.get("chunk_text", ""),
                        "category": fields.get("category", "其他"),
                        "entities": fields.get("entities", ""),
                        "timestamp": fields.get("timestamp", ""),
                        "score": hit._score
                    })

            logger.info(
                f"🔍 Pinecone 搜尋 '{query[:20]}...' → {len(memories)} 筆結果"
            )
            return memories

        except Exception as e:
            logger.error(f"❌ Pinecone 搜尋失敗: {e}")
            return []

    def delete_memory(self, memory_id: str) -> bool:
        """刪除指定記憶"""
        if not self.enabled:
            return False

        try:
            self.index.delete(
                ids=[memory_id],
                namespace=self.namespace
            )
            logger.info(f"🗑️ Pinecone 已刪除: {memory_id}")
            return True
        except Exception as e:
            logger.error(f"❌ Pinecone 刪除失敗: {e}")
            return False

    def update_memory(self, memory_id: str, fact: str,
                      category: str = "其他",
                      entities: list = None,
                      timestamp: str = None) -> bool:
        """更新記憶（upsert_records 即為更新）"""
        return self.upsert_memory(memory_id, fact, category,
                                  entities, timestamp)
