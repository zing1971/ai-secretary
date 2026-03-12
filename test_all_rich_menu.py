import os
import json
from dotenv import load_dotenv
from intent_router import IntentRouter

# 強制重新載入環境變數
load_dotenv(override=True)

def test_rich_menu():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY not found in .env")
        return

    router = IntentRouter(api_key=api_key)

    test_cases = [
        # Alice 區
        {"tag": "A1", "msg": "查詢我未來2天的行程安排，提醒需要準備的事項"},
        {"tag": "A2", "msg": "摘要最新15封郵件重點，標註需要回覆的信"},
        {"tag": "A3", "msg": "上網搜尋今天的科技產業與資安重要新聞"},
        {"tag": "A4", "msg": "查詢資安知識庫，整理最新威脅情報與防護建議"},
        {"tag": "A5", "msg": "列出所有待辦事項，依緊急程度排序"},
        {"tag": "A6", "msg": "搜尋雲端硬碟本週更新的檔案清單"},
        
        # Birdie 區
        {"tag": "B1", "msg": "今日簡報"},
        {"tag": "B2", "msg": "檢查最新郵件，挑出需要答覆的信協助草擬"},
        {"tag": "B3", "msg": "整理雲端，分析目錄結構並提出分類建議"},
        {"tag": "B4", "msg": "我要傳照片給你辨識，請準備接收名片、海報或會議筆記"},
        {"tag": "B5", "msg": "告訴我你們目前知道關於我的所有偏好設定和重要備忘"},
        {"tag": "B6", "msg": "你們好，簡要說明你們各自能提供的服務項目"},
    ]

    print(f"{'Tag':<5} | {'Message':<60} | {'Intent':<20} | {'Status'}")
    print("-" * 100)

    results = []
    for case in test_cases:
        msg = case["msg"]
        tag = case["tag"]
        try:
            # 我們這裡要觀察是規則命中還是 LLM 命中
            # 為了測試，我們稍微修改一下 router 的 classify_intent 來回傳來源
            # 但不改源碼，改用比較輸出的方式
            
            # 手動模擬分類過程
            rule_result = router._rule_based_classify(msg)
            if rule_result:
                source = "Rule"
                intent_data = rule_result
            else:
                source = "LLM"
                intent_data = router._llm_classify(msg)
            
            intent = intent_data.get("intent", "Unknown")
            print(f"{tag:<5} | {msg[:60]:<60} | {intent:<20} | {source}")
            
            results.append({
                "tag": tag,
                "msg": msg,
                "intent_data": intent_data,
                "source": source
            })
            
        except Exception as e:
            print(f"{tag:<5} | {msg[:60]:<60} | Error: {str(e)[:15]:<13} | FAILED")

    # 詳細參數檢查
    print("\n=== 詳細檢查項目 ===")
    for res in results:
        tag = res["tag"]
        data = res["intent_data"]
        source = res["source"]
        
        print(f"\n[{tag}] {res['msg']}")
        print(f"Source: {source}")
        print(f"Intent: {data.get('intent')}")
        
        # 檢查關鍵參數
        if tag == "A1": # 預期 offset 0-1
             tr = data.get("time_range", {})
             if tr.get("start_offset") == 0 and tr.get("end_offset") == 1:
                 print("✅ Time range correct (0 to 1)")
             else:
                 print(f"❌ Time range unexpected: {tr}")
        
        if tag == "A2": # 預期 Query_Email
            if data.get("intent") == "Query_Email":
                print("✅ Intent correct")
            else:
                print(f"❌ Intent mismatch: {data.get('intent')}")

        if tag == "A4": # 預期 domain: infosec
            if data.get("domain") == "infosec":
                print("✅ Domain correct")
            else:
                print(f"❌ Domain mismatch: {data.get('domain')}")

        if tag == "B2": # 預期 Query_Email + 轉交標記
            if data.get("intent") == "Query_Email":
                 print("✅ Intent correct (Query_Email for Birdie handoff)")
            else:
                 print(f"❌ Intent mismatch: {data.get('intent')}")

        if tag == "B4": # 預期 Visual_Assistant
            if data.get("intent") == "Visual_Assistant":
                print("✅ Intent correct")
            else:
                print(f"❌ Intent mismatch: {data.get('intent')}")

if __name__ == "__main__":
    test_rich_menu()
