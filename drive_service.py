"""
Google Drive API 服務模組

提供 Drive 低階操作：列出檔案、建立資料夾、移動檔案。
只掃描根目錄散檔（非資料夾內的檔案）。
"""
import logging

logger = logging.getLogger(__name__)

# Google Drive 資料夾 MIME 類型
FOLDER_MIME = "application/vnd.google-apps.folder"


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
