"""
摘要技能：使用 Gemini Flash 對文字、信件或 Drive 檔案產生條列摘要。
直接呼叫 Google REST API，不經過 hermes 代理。
"""

import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))

import json as _json
import urllib.request as _urllib_req
import urllib.parse as _urllib_parse

_MODEL = "gemini-2.5-flash"
_BASE = "https://generativelanguage.googleapis.com/v1beta/models"
_MAX_INPUT = 8000


def _call_gemini(prompt: str) -> str:
    api_key = _os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY 未設定，無法使用摘要功能")

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.2, "maxOutputTokens": 1024},
    }
    url = f"{_BASE}/{_MODEL}:generateContent?{_urllib_parse.urlencode({'key': api_key})}"
    req = _urllib_req.Request(
        url,
        data=_json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with _urllib_req.urlopen(req, timeout=30) as resp:
        result = _json.loads(resp.read().decode("utf-8"))

    try:
        return result["candidates"][0]["content"]["parts"][0]["text"].strip()
    except (KeyError, IndexError) as exc:
        candidates = result.get("candidates", [])
        finish_reason = (
            candidates[0].get("finishReason", "unknown") if candidates else "no_candidates"
        )
        raise RuntimeError(
            f"摘要 API 回傳格式異常，finishReason={finish_reason}"
        ) from exc


def summarize_text(text: str, lang: str = "繁體中文") -> str:
    """
    對輸入文字產生條列摘要。

    Args:
        text: 要摘要的文字（必填）。
        lang: 摘要輸出語言（預設 "繁體中文"）。
    """
    if len(text) > _MAX_INPUT:
        text = text[:_MAX_INPUT] + "\n…（已截斷）"
    prompt = (
        f"請以「{lang}」撰寫以下內容的重點摘要（條列式，5 點以內）：\n\n{text}"
    )
    return _call_gemini(prompt)


def summarize_email(email_id: str, lang: str = "繁體中文") -> str:
    """
    讀取指定 Gmail 信件並產生摘要。

    Args:
        email_id: Gmail 信件 ID（必填）。
        lang: 摘要輸出語言（預設 "繁體中文"）。
    """
    from gmail_skills import read_email
    content = read_email(email_id)
    return summarize_text(content, lang)


def summarize_file(file_id: str, lang: str = "繁體中文") -> str:
    """
    讀取指定 Drive 檔案並產生摘要。

    Args:
        file_id: Drive 檔案 ID（必填）。
        lang: 摘要輸出語言（預設 "繁體中文"）。
    """
    from drive_skills import read_drive_file
    content = read_drive_file(file_id)
    return summarize_text(content, lang)
