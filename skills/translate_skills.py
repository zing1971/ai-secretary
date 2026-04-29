"""
翻譯技能：使用 Gemini Flash 進行多語言翻譯。
直接呼叫 Google REST API，不經過 hermes 代理。
"""

import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))

import json as _json
import urllib.request as _urllib_req
import urllib.parse as _urllib_parse

_MODEL = "gemini-2.5-flash"
_BASE = "https://generativelanguage.googleapis.com/v1beta/models"


def translate_text(text: str, to_lang: str, from_lang: str = None) -> str:
    """
    翻譯文字至指定語言。

    Args:
        text: 要翻譯的文字（必填）。
        to_lang: 目標語言，例如 "繁體中文"、"English"、"日本語"、"Spanish"。
        from_lang: 來源語言（可選，不填則自動偵測）。
    """
    api_key = _os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY 未設定，無法使用翻譯功能")

    src_hint = f"從「{from_lang}」" if from_lang else ""
    prompt = (
        f"請{src_hint}翻譯以下文字至「{to_lang}」。\n"
        f"只輸出翻譯結果，不加任何說明或解釋。\n\n"
        f"{text}"
    )

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.1, "maxOutputTokens": 4096},
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
            f"翻譯 API 回傳格式異常，finishReason={finish_reason}"
        ) from exc
