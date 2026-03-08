import json
import os
from dotenv import load_dotenv
from intent_router import IntentRouter

load_dotenv(override=True)
router = IntentRouter(api_key=os.getenv("GEMINI_API_KEY"))

msgs = [
    "查詢有關星宇的郵件",
    "明天行程",
    "尋找企劃書檔案"
]

print("=== 規則式結果 ===")
for m in msgs:
    print(f"\n[{m}]")
    print(json.dumps(router._rule_based_classify(m), indent=2, ensure_ascii=False))

print("\n=== LLM 結果 ===")
for m in msgs:
    print(f"\n[{m}]")
    print(json.dumps(router._llm_classify(m), indent=2, ensure_ascii=False))
