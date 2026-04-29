"""
Google Sheets API 服務模組

提供 Sheets 低階操作：讀取指定 range 的儲存格資料。
"""
import logging

logger = logging.getLogger(__name__)

_MAX_ROWS = 200


class SheetsService:
    """Google Sheets API 操作封裝"""

    def __init__(self, service):
        self.service = service

    def read_range(self, spreadsheet_id: str, range_name: str = None) -> dict:
        """
        讀取試算表指定範圍的資料。

        Args:
            spreadsheet_id: 試算表 ID
            range_name: 範圍，例如 "Sheet1!A1:E20"（不填則讀取第一個工作表全部）

        Returns:
            dict: {title, range, rows: [[cell, ...]]}

        Raises:
            RuntimeError: 試算表不存在或讀取失敗。
        """
        try:
            meta = self.service.spreadsheets().get(
                spreadsheetId=spreadsheet_id,
                fields="properties/title,sheets/properties/title",
            ).execute()
        except Exception as exc:
            raise RuntimeError(
                f"找不到試算表 (id={spreadsheet_id})：{exc}"
            ) from exc

        title = meta["properties"]["title"]
        sheets = meta.get("sheets", [])
        first_sheet = sheets[0]["properties"]["title"] if sheets else "Sheet1"

        if not range_name:
            range_name = f"'{first_sheet}'"

        try:
            result = self.service.spreadsheets().values().get(
                spreadsheetId=spreadsheet_id,
                range=range_name,
                majorDimension="ROWS",
            ).execute()
        except Exception as exc:
            raise RuntimeError(
                f"讀取範圍 '{range_name}' 失敗：{exc}"
            ) from exc

        rows = result.get("values", [])
        if len(rows) > _MAX_ROWS:
            rows = rows[:_MAX_ROWS]

        logger.info("📊 讀取試算表 '%s' 範圍 %s: %d 列", title, range_name, len(rows))
        return {"title": title, "range": result.get("range", range_name), "rows": rows}
