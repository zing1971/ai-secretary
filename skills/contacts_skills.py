"""
Google Contacts 技能：建立聯絡人、搜尋聯絡人。
"""

import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))

from _skill_base import _PEOPLE_IDX, _require_service
from contacts_service import (
    CONTACT_LABELS,
    create_contact as _create_contact,
    search_contacts as _search_contacts,
)

_LABEL_LIST = "、".join(CONTACT_LABELS)


def create_contact_entry(
    name: str,
    email: str,
    phone: str = None,
    company: str = None,
    job_title: str = None,
    label: str = None,
) -> str:
    """
    在 Google Contacts 中建立一筆新聯絡人。

    Args:
        name: 姓名（必填）。
        email: Email 地址（必填）。
        phone: 電話號碼（可選）。
        company: 公司名稱（可選）。
        job_title: 職稱（可選）。
        label: 分類標籤（可選）。可用值：政府機關、學術研究、廠商代表、關鍵夥伴、媒體公關、其他。
    """
    service = _require_service(_PEOPLE_IDX, "Google Contacts")
    result = _create_contact(
        service,
        name=name,
        company=company or "",
        job_title=job_title or "",
        email=email,
        phone=phone or "",
        label=label,
    )
    if not result:
        raise RuntimeError(f"建立聯絡人失敗（name={name!r}）")
    resource_name = result.get("resourceName", "")
    label_str = f" | 標籤：{label}" if label else ""
    return f"✅ 已建立聯絡人：{name}{label_str}\n  資源 ID：{resource_name}"


def search_contacts(query: str, max_results: int = 10) -> str:
    """
    根據關鍵字搜尋 Google Contacts 中的聯絡人（姓名、Email、公司）。

    Args:
        query: 搜尋關鍵字，可為姓名片段、Email 或公司名稱（必填）。
        max_results: 最多回傳幾筆結果（預設 10）。
    """
    service = _require_service(_PEOPLE_IDX, "Google Contacts")
    contacts = _search_contacts(service, query, max_results)
    if not contacts:
        return f"找不到包含「{query}」的聯絡人。"

    lines = []
    for c in contacts:
        parts = [f"• {c['name']}"]
        org_parts = list(filter(None, [c.get("company", ""), c.get("job_title", "")]))
        if org_parts:
            parts.append(f"  🏢 {' / '.join(org_parts)}")
        if c.get("email"):
            parts.append(f"  📧 {c['email']}")
        if c.get("phone"):
            parts.append(f"  📞 {c['phone']}")
        lines.append("\n".join(parts))
    return "\n\n".join(lines)
