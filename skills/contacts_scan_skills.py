"""
名片掃描技能：圖片辨識 → 自動建立 Google 聯絡人。
"""

import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))

import json as _json
import re as _re

from generation_skills import analyze_image
from contacts_skills import create_contact_entry

_CARD_PROMPT = (
    "這是一張名片，請仔細辨識所有文字，以 JSON 格式輸出以下欄位："
    '{"name": "姓名", "title": "職稱", "company": "公司名稱", '
    '"email": "電子郵件", "phone": "電話號碼", "address": "地址"}。'
    "若欄位不存在請設為 null。只輸出 JSON，不加任何說明文字。"
)


def scan_business_card(image_file: str = None, image_url: str = None) -> str:
    """
    辨識名片圖片並自動建立 Google 聯絡人。

    Args:
        image_file: 本地圖片檔案路徑（與 image_url 二擇一）。
        image_url: 圖片 URL（與 image_file 二擇一）。
    """
    raw = analyze_image(image_url=image_url, image_file=image_file, prompt=_CARD_PROMPT)

    json_match = _re.search(r'\{[^{}]*\}', raw, _re.DOTALL)
    if not json_match:
        return f"❌ 無法從圖片解析聯絡資訊\n\n辨識結果：\n{raw}"

    try:
        info = _json.loads(json_match.group())
    except _json.JSONDecodeError:
        return f"❌ JSON 解析失敗\n\n辨識結果：\n{raw}"

    name = info.get("name")
    email = info.get("email")

    if not name:
        return f"❌ 無法辨識姓名\n\n辨識結果：\n{raw}"
    if not email:
        return f"❌ 無法辨識 Email（辨識到姓名：{name}）\n\n辨識結果：\n{raw}"

    return create_contact_entry(
        name=name,
        email=email,
        phone=info.get("phone"),
        company=info.get("company"),
        job_title=info.get("title"),
        label=None,
    )
