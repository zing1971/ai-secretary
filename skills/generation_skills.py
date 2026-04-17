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
