"""
生成技能：使用 Gemini 2.5 Pro 進行高品質長文生成任務。
Flash 負責查詢／回覆；Pro 負責需要深度思考的創作與分析。
適用場景：正式信件、報告、會議摘要、企劃書、新聞稿等。
"""

import os

from google import genai
from google.genai import types

_PRO_MODEL = "gemini-2.5-pro"
_SYSTEM_PROMPT = (
    "你是仁哥（zing1971@gmail.com）的資深全能特助艾莉絲（Alice）。"
    "請以繁體中文、專業且有溫度的語氣完成以下任務。"
    "輸出格式清晰，善用 Markdown 的標題、列表與粗體。"
)


def _pro_client() -> genai.Client:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY 未設定，無法使用 Gemini 2.5 Pro")
    return genai.Client(api_key=api_key)


def draft_professional_content(task: str, context: str = None) -> str:
    """
    使用 Gemini 2.5 Pro 起草高品質的專業內容。
    Flash 處理查詢，Pro 處理創作——適合需要較高生成品質的任務。

    適用場景：
    - 正式信件（感謝信、邀請函、道歉信）
    - 報告與執行摘要
    - 會議記錄整理
    - 企劃書、提案、新聞稿
    - 需要深度分析的長文

    Args:
        task: 任務描述，例如「起草一封感謝信給王大明董事長，感謝他上週的引薦」
              或「撰寫本次 Q1 業績季報的執行摘要」。
        context: 背景資訊（可選）：會議記錄、相關事實、參考資料、
                 收件人資訊等，提供越詳細品質越好。
    """
    client = _pro_client()

    prompt = task if not context else f"任務：{task}\n\n背景資訊：\n{context}"

    response = client.models.generate_content(
        model=_PRO_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=_SYSTEM_PROMPT,
            temperature=0.7,
        ),
    )

    text = getattr(response, "text", None)
    if not text:
        raise RuntimeError("Gemini 2.5 Pro 回傳空結果，請稍後重試")

    return f"📝 *（Gemini 2.5 Pro 生成）*\n\n{text}"


def analyze_image(
    image_url: str = None,
    image_file: str = None,
    prompt: str = "請描述並提取圖片中的所有文字資訊",
) -> str:
    """
    使用 Gemini 原生視覺能力分析圖片（名片掃描、圖片 OCR 等）。

    直接呼叫 Google Generative Language REST API，完全繞過 google-genai SDK，
    確保不經過 OpenRouter 或任何第三方代理。

    Args:
        image_url:  圖片 URL（支援 http/https，包含 Telegram file URL）。
        image_file: 本地圖片檔案路徑（與 image_url 擇一）。
        prompt:     給 Gemini 的分析提示，預設為名片文字提取。
    """
    import base64
    import mimetypes
    import urllib.request
    import urllib.parse
    import json as _json

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY 未設定")

    # ── 讀取圖片 bytes ─────────────────────────────────────────────────────────
    if image_file:
        with open(image_file, "rb") as f:
            image_data = f.read()
        mime_type, _ = mimetypes.guess_type(image_file)
        mime_type = mime_type or "image/jpeg"

    elif image_url:
        req = urllib.request.Request(
            image_url,
            headers={"User-Agent": "Mozilla/5.0 AliceBot/1.0"},
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            image_data = resp.read()
            content_type = resp.headers.get("Content-Type", "image/jpeg")
            mime_type = content_type.split(";")[0].strip()

    else:
        raise RuntimeError("analyze_image：需要提供 image_url 或 image_file")

    # ── 直接呼叫 Google REST API（繞過 SDK，避免 hermes OpenRouter 代理）──────
    image_b64 = base64.b64encode(image_data).decode("utf-8")

    payload = {
        "contents": [{
            "parts": [
                {"text": prompt},
                {"inline_data": {"mime_type": mime_type, "data": image_b64}},
            ]
        }],
        "generationConfig": {"maxOutputTokens": 1024},
    }

    # API key 以 query param 傳送（Google REST API 標準做法）
    # 使用 urlencode 確保 key 不直接出現在 f-string 中（避免 traceback 洩漏）
    _base = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
    api_url = f"{_base}?{urllib.parse.urlencode({'key': api_key})}"

    req = urllib.request.Request(
        api_url,
        data=_json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        result = _json.loads(resp.read().decode("utf-8"))

    try:
        text = result["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError) as exc:
        # 僅記錄安全摘要，避免將完整 result（可能含請求資訊）洩漏至錯誤訊息
        candidates = result.get("candidates", [])
        finish_reason = (
            candidates[0].get("finishReason", "unknown") if candidates else "no_candidates"
        )
        raise RuntimeError(
            f"Gemini 視覺 API 回傳格式異常，finishReason={finish_reason}"
        ) from exc

    return text
