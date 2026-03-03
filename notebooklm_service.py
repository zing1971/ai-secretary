import subprocess
import os
import logging
from config import Config

logger = logging.getLogger("AI-Secretary")

class NotebookLMService:
    def __init__(self):
        # 預設路徑 (Windows 環境下技能安裝位置)
        self.skill_dir = r"C:\Users\zing\.gemini\antigravity\skills\notebooklm-skill"
        self.run_py = os.path.join(self.skill_dir, "scripts", "run.py")
        self.ask_question_py = "ask_question.py"
        
        # 建立領域與 ID 的對照
        self.notebook_map = {
            "infosec": Config.NOTEBOOK_ID_INFOSEC,
            "it": Config.NOTEBOOK_ID_IT,
            "trends": Config.NOTEBOOK_ID_TRENDS
        }

    def query_advisor(self, query: str, domain: str = "it") -> dict:
        """
        向 NotebookLM 專家查詢資訊
        
        Args:
            query: 使用者的提問
            domain: 領域 (infosec / it / trends)
            
        Returns:
            dict: {"answer": str, "has_followup": bool}
        """
        notebook_id = self.notebook_map.get(domain, Config.NOTEBOOK_ID_IT)
        
        if not notebook_id:
            logger.warning(f"⚠️ 領域 {domain} 未設定正確的 Notebook ID，回退至 IT 庫")
            notebook_id = Config.NOTEBOOK_ID_IT
            
        if not notebook_id:
            return {"answer": "抱歉，目前尚未設定相關領域的知識庫 ID，無法為您查詢 🙇‍♀️", "has_followup": False}

        logger.info(f"🔍 正在向 NotebookLM 查詢 (領域: {domain}, ID: {notebook_id})...")
        
        try:
            # 建立完整 URL
            notebook_url = f"https://notebooklm.google.com/notebook/{notebook_id}"
            
            # 呼叫技能腳本
            # python scripts/run.py ask_question.py --question "..." --notebook-url ...
            cmd = [
                "python", 
                self.run_py, 
                self.ask_question_py, 
                "--question", query, 
                "--notebook-url", notebook_url
            ]
            
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                encoding='utf-8', 
                errors='ignore',
                cwd=self.skill_dir # 切換至技能目錄執行
            )
            
            if result.returncode != 0:
                logger.error(f"❌ NotebookLM 腳本執行失敗: {result.stderr}")
                return {"answer": "抱歉，我在查閱知識庫時遇到了一些技術問題 🙇‍♀️", "has_followup": False}
            
            stdout = result.stdout
            
            # 解析回答。腳本通常會在結尾輸出答案。
            # 尋找是否包含追問信號
            has_followup = "EXTREMELY IMPORTANT: Is that ALL you need to know?" in stdout
            
            # 清理輸出，只保留答案部分
            # 技巧：ask_question.py 通常會輸出很多日誌，最後才是答案。
            # 如果有 "ANSWER:" 標籤會更好，但根據 SKILL.md，它是直接輸出答案的。
            # 我們假設 stdout 的最後一部分是答案。
            
            # 移除追問提示
            clean_answer = stdout.replace("EXTREMELY IMPORTANT: Is that ALL you need to know?", "").strip()
            
            # 移除終端機裝飾符號
            lines = clean_answer.split('\n')
            final_lines = []
            capture = False
            
            # 簡單的過濾邏輯：移除載入中、環境啟動等日誌 (這裡根據實際 run.py 輸出調整)
            # 假設前面的日誌帶有 ⚙️ 或 📚 或 🚀
            for line in lines:
                if any(x in line for x in ["⚙️", "📚", "🚀", "Activation", "Installing", "Checking auth"]):
                    continue
                final_lines.append(line)
            
            answer_text = "\n".join(final_lines).strip()
            
            if not answer_text:
                answer_text = "抱歉，從知識庫中沒有找到相關的明確答案。"
                
            return {"answer": answer_text, "has_followup": has_followup}
            
        except Exception as e:
            logger.error(f"❌ query_advisor 發生例外: {e}")
            return {"answer": f"抱歉，查詢過程中發生錯誤：{str(e)}", "has_followup": False}
