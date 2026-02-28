import datetime
import logging
from config import Config

logger = logging.getLogger(__name__)

class MemoryService:
    def __init__(self, sheets_service):
        self.service = sheets_service
        self.spreadsheet_id = Config.GOOGLE_SHEET_ID
        self.range_name = None  # 將在运行时動態偵測

    def _ensure_range_name(self):
        """動態取得第一張工作算的名稱"""
        if self.range_name:
            return True
        try:
            spreadsheet = self.service.spreadsheets().get(spreadsheetId=self.spreadsheet_id).execute()
            sheet_title = spreadsheet['sheets'][0]['properties']['title']
            self.range_name = f"'{sheet_title}'!A:B"
            logger.info(f"📌 偵測到記憶工作表: {self.range_name}")
            return True
        except Exception as e:
            logger.error(f"❌ 無法取得工作表資訊: {e}")
            return False

    def save_memory(self, fact: str) -> bool:
        """將事實存入 Google Sheets"""
        if not self._ensure_range_name():
            return False
        try:
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            values = [[timestamp, fact]]
            body = {'values': values}
            
            result = self.service.spreadsheets().values().append(
                spreadsheetId=self.spreadsheet_id,
                range=self.range_name,
                valueInputOption='RAW',
                body=body
            ).execute()
            
            logger.info(f"✅ 成功存入記憶: {fact}")
            return True
        except Exception as e:
            logger.error(f"❌ 存入記憶失敗: {str(e)}")
            return False

    def fetch_all_memories(self) -> str:
        """取得所有記憶事實，並格式化為字串供 LLM 使用"""
        if not self._ensure_range_name():
            return "無法取得長期記憶環境。"
        try:
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range=self.range_name
            ).execute()
            
            rows = result.get('values', [])
            if not rows:
                return "目前沒有儲存任何特定的偏好或記憶。"
            
            # 過濾掉可能存在的標題列 (如果有)
            memories = []
            for row in rows:
                if len(row) >= 2:
                    memories.append(f"- {row[1]}")
            
            return "\n".join(memories)
        except Exception as e:
            logger.error(f"❌ 取得記憶失敗: {str(e)}")
            return "無法取得長期記憶環境。"
