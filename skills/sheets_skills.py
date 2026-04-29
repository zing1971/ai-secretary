"""
Google Sheets 技能：讀取試算表內容。
"""

import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))

from _skill_base import _SHEETS_IDX, _require_service
from sheets_service import SheetsService


def write_sheet(spreadsheet_id: str, range_name: str, values_str: str) -> str:
    """
    寫入 Google Sheets 試算表儲存格。

    Args:
        spreadsheet_id: 試算表 ID（必填）。
        range_name: 寫入起始範圍，例如 "Sheet1!A1"（必填）。
        values_str: 儲存格內容。單列用逗號分隔 "v1,v2,v3"；
                    多列用 | 分隔列 "r1c1,r1c2|r2c1,r2c2"（必填）。
    """
    service = _require_service(_SHEETS_IDX, "Google Sheets")
    ss = SheetsService(service)
    rows = [
        [cell.strip() for cell in row.split(",")]
        for row in values_str.split("|")
    ]
    result = ss.write_range(spreadsheet_id, range_name, rows)
    updated_cells = result.get("updatedCells", 0)
    updated_range = result.get("updatedRange", range_name)
    return f"✅ 已寫入 {updated_cells} 個儲存格到 {updated_range}"


def read_sheet(spreadsheet_id: str, range_name: str = None) -> str:
    """
    讀取 Google Sheets 試算表，以表格格式輸出。

    Args:
        spreadsheet_id: 試算表 ID（必填）。
        range_name: 讀取範圍，例如 "Sheet1!A1:E20"（可選，預設讀整個第一個工作表）。
    """
    service = _require_service(_SHEETS_IDX, "Google Sheets")
    ss = SheetsService(service)
    data = ss.read_range(spreadsheet_id, range_name)

    rows = data["rows"]
    if not rows:
        return f"📊 {data['title']} — 沒有資料"

    max_cols = max(len(r) for r in rows)
    padded = [r + [""] * (max_cols - len(r)) for r in rows]
    col_widths = [
        max(len(str(padded[i][j])) for i in range(len(padded)))
        for j in range(max_cols)
    ]

    lines = []
    for i, row in enumerate(padded):
        line = " | ".join(str(cell).ljust(col_widths[j]) for j, cell in enumerate(row))
        lines.append(line)
        if i == 0:
            lines.append("-" * len(line))

    return f"📊 {data['title']} ({data['range']})\n\n" + "\n".join(lines)
