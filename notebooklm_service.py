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
            
            # 設定環境變數強制使用 UTF-8 輸出，避免 Windows CP950 編碼問題
            env = os.environ.copy()
            env["PYTHONIOENCODING"] = "utf-8"
            
            result = subprocess.run(
                cmd, 
                env=env,
                capture_output=True, 
                text=True, 
                encoding='utf-8', 
                errors='ignore',
                timeout=180, # 3 分鐘超時保護
                cwd=self.skill_dir
            )
            
            if result.returncode != 0:
                logger.error(f"❌ NotebookLM 腳本執行失敗 (ReturnCode: {result.returncode})")
                logger.error(f"STDOUT: {result.stdout}")
                logger.error(f"STDERR: {result.stderr}")
                return {"answer": "抱歉，我在查閱知識庫時遇到了一些技術問題 🙇‍♀️", "has_followup": False}
            
            stdout = result.stdout
            
            # 解析回答。使用明確的標記 [RESULT_START] 與 [RESULT_END]
            if "[RESULT_START]" in stdout and "[RESULT_END]" in stdout:
                answer_part = stdout.split("[RESULT_START]")[1].split("[RESULT_END]")[0].strip()
            else:
                # 備援方案：如果沒有標記，嘗試舊的過濾邏輯
                clean_answer = stdout.replace("EXTREMELY IMPORTANT: Is that ALL you need to know?", "").strip()
                lines = clean_answer.split('\n')
                final_lines = []
                for line in lines:
                    # 過濾各種日誌前綴與 Emoji
                    if any(x in line for x in ["⚙️", "📚", "🚀", "Activation", "Installing", "Checking auth", "Found input", "Typing", "Submitting", "Waiting for", "🌐", "⏳", "📤", "✅", "💬", "⚠️"]):
                        continue
                    # 移除分隔線
                    if line.startswith("==="):
                        continue
                    final_lines.append(line)
                answer_part = "\n".join(final_lines).strip()
            
            # 尋找是否包含追問信號
            has_followup = "EXTREMELY IMPORTANT: Is that ALL you need to know?" in stdout
            
            # 移除追問提示（如果還在裡面）
            answer_text = answer_part.replace("EXTREMELY IMPORTANT: Is that ALL you need to know?", "").strip()
            
            if not answer_text or len(answer_text) < 10:
                # 如果解析出的文字太短，可能解析失敗，紀錄警告並嘗試從最後幾行獲取
                logger.warning(f"⚠️ 解析出的答案太短或為空。原始輸出長度: {len(stdout)}")
                if not answer_text:
                    answer_text = "抱歉，從知識庫中解析答案失敗，請聯繫管理員檢查系統日誌。"
                
            return {"answer": answer_text, "has_followup": has_followup}
            
        except Exception as e:
            logger.error(f"❌ query_advisor 發生例外: {e}")
            return {"answer": f"抱歉，查詢過程中發生錯誤：{str(e)}", "has_followup": False}
