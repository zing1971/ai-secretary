"""
Google Drive API 服務模組

提供 Drive 低階操作：列出檔案、建立資料夾、移動檔案、讀取檔案內容。
只掃描根目錄散檔（非資料夾內的檔案）。
"""
import logging

logger = logging.getLogger(__name__)

# Google Drive 資料夾 MIME 類型
FOLDER_MIME = "application/vnd.google-apps.folder"

# Google Workspace 格式 → 匯出格式對照表
_EXPORT_MAP = {
    "application/vnd.google-apps.document": "text/plain",
    "application/vnd.google-apps.spreadsheet": "text/csv",
    "application/vnd.google-apps.presentation": "text/plain",
}

_READ_MAX_CHARS = 4000


class DriveService:
    """Google Drive API 操作封裝"""

    def __init__(self, service):
        self.service = service

    def list_root_files(self, max_results=100) -> list:
        """
        列出根目錄的散檔（不含資料夾）。

        Returns:
            list of dict: [{id, name, mimeType, size, modifiedTime}]
        """
        try:
            query = "'root' in parents and trashed = false and mimeType != 'application/vnd.google-apps.folder'"
            results = self.service.files().list(
                q=query,
                pageSize=max_results,
                fields="files(id, name, mimeType, size, modifiedTime)",
                orderBy="modifiedTime desc"
            ).execute()

            files = results.get("files", [])
            logger.info(f"📂 根目錄散檔: {len(files)} 個")
            return files

        except Exception as e:
            logger.error(f"❌ 列出 Drive 檔案失敗: {e}")
            return []

    def list_root_folders(self) -> list:
        """
        列出根目錄的資料夾。

        Returns:
            list of dict: [{id, name}]
        """
        try:
            query = "'root' in parents and trashed = false and mimeType = 'application/vnd.google-apps.folder'"
            results = self.service.files().list(
                q=query,
                pageSize=100,
                fields="files(id, name)",
                orderBy="name"
            ).execute()

            folders = results.get("files", [])
            logger.info(f"📁 根目錄資料夾: {len(folders)} 個")
            return folders

        except Exception as e:
            logger.error(f"❌ 列出資料夾失敗: {e}")
            return []

    def create_folder(self, name: str, parent_id: str = "root") -> str:
        """
        建立新資料夾。

        Returns:
            str: 新資料夾的 ID，失敗回傳 None
        """
        try:
            metadata = {
                "name": name,
                "mimeType": FOLDER_MIME,
                "parents": [parent_id]
            }
            folder = self.service.files().create(
                body=metadata,
                fields="id"
            ).execute()

            folder_id = folder.get("id")
            logger.info(f"📁 建立資料夾: {name} ({folder_id})")
            return folder_id

        except Exception as e:
            logger.error(f"❌ 建立資料夾失敗 '{name}': {e}")
            return None

    def move_file(self, file_id: str, new_parent_id: str) -> bool:
        """
        移動檔案到指定資料夾。

        Args:
            file_id: 要移動的檔案 ID
            new_parent_id: 目標資料夾 ID
        """
        try:
            # 先取得目前的 parents
            file_info = self.service.files().get(
                fileId=file_id,
                fields="parents"
            ).execute()
            old_parents = ",".join(file_info.get("parents", []))

            # 移動檔案
            self.service.files().update(
                fileId=file_id,
                addParents=new_parent_id,
                removeParents=old_parents,
                fields="id, parents"
            ).execute()

            logger.info(f"📦 已移動檔案 {file_id} → {new_parent_id}")
            return True

        except Exception as e:
            logger.error(f"❌ 移動檔案失敗 {file_id}: {e}")
            return False

    def get_file_name(self, file_id: str) -> str:
        """取得檔案名稱"""
        try:
            result = self.service.files().get(
                fileId=file_id, fields="name"
            ).execute()
            return result.get("name", "")
        except Exception:
            return ""

    def read_file(self, file_id: str) -> dict:
        """
        讀取 Drive 檔案的文字內容。

        Google Workspace 格式（Docs/Sheets/Slides）自動匯出為純文字/CSV；
        一般文字檔直接下載。內容超過 _READ_MAX_CHARS 時截斷。

        Returns:
            dict: {name, mimeType, content}

        Raises:
            RuntimeError: 檔案不存在或讀取失敗。
        """
        try:
            meta = self.service.files().get(
                fileId=file_id, fields="name,mimeType"
            ).execute()
        except Exception as exc:
            raise RuntimeError(f"找不到檔案 (file_id={file_id})：{exc}") from exc

        name = meta["name"]
        mime = meta["mimeType"]

        try:
            if mime in _EXPORT_MAP:
                content_bytes = self.service.files().export(
                    fileId=file_id, mimeType=_EXPORT_MAP[mime]
                ).execute()
            else:
                content_bytes = self.service.files().get_media(
                    fileId=file_id
                ).execute()
        except Exception as exc:
            raise RuntimeError(f"讀取檔案內容失敗 (file_id={file_id})：{exc}") from exc

        content = (
            content_bytes.decode("utf-8", errors="replace")
            if isinstance(content_bytes, bytes)
            else str(content_bytes)
        )
        if len(content) > _READ_MAX_CHARS:
            content = content[:_READ_MAX_CHARS] + f"\n\n…（已截斷，原始長度 {len(content)} 字元）"

        logger.info("📄 讀取 Drive 檔案：%s (%s)", name, mime)
        return {"name": name, "mimeType": mime, "content": content}

    def search_files_by_keyword(self, keyword: str, max_results: int = 5) -> list:
        """
        根據關鍵字搜尋 Google Drive 中的檔案（包含檔名與內文）。

        Args:
            keyword: 搜尋關鍵字
            max_results: 最多回傳幾筆結果，預設為 5

        Returns:
            list of dict: [{id, name, webViewLink, mimeType, modifiedTime}]
        """
        try:
            # fullText 會搜尋檔案名稱及檔案內容文字
            # 排除已丟垃圾桶的檔案
            query = f"trashed = false and fullText contains '{keyword}'"
            results = self.service.files().list(
                q=query,
                pageSize=max_results,
                fields="files(id, name, webViewLink, mimeType, modifiedTime)",
                orderBy="modifiedTime desc" # 依修改時間排序，最新的在前
            ).execute()

            files = results.get("files", [])
            logger.info(f"🔍 Drive 搜尋 '{keyword}': 找到 {len(files)} 個檔案")
            return files

        except Exception as e:
            logger.error(f"❌ 搜尋 Drive 檔案失敗 '{keyword}': {e}")
            return []
