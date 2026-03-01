"""
Google Drive 整理代理

三階段互動流程：
1. 掃描根目錄 → AI 分析 → 產生提案
2. 推送提案到 LINE → 等待使用者確認
3. 執行整理 → 產生報告

安全機制：
- 提案須經使用者確認才執行
- 30 分鐘未確認自動過期
- 只做分類/移動，不做刪除
"""
import logging
import time

logger = logging.getLogger(__name__)

# 提案暫存（key=user_id, value=proposal dict）
_pending_proposals = {}

# 提案過期時間（秒）
PROPOSAL_TTL = 1800  # 30 分鐘


class DriveOrganizer:
    """Google Drive 智慧整理代理"""

    def __init__(self, drive_service, llm_service):
        """
        Args:
            drive_service: DriveService 實例
            llm_service: LLMService 實例
        """
        self.drive = drive_service
        self.llm = llm_service

    def scan_and_propose(self, user_id: str) -> str:
        """
        掃描 Drive 根目錄並產生整理提案。

        Returns:
            str: 提案文字（推送給 LINE）
        """
        if not self.drive:
            return "仁哥抱歉，Google Drive 服務未就緒，Alice 暫時無法整理 🙇‍♀️"

        # 1. 掃描根目錄
        logger.info("📂 開始掃描 Drive 根目錄...")
        loose_files = self.drive.list_root_files()
        folders = self.drive.list_root_folders()

        if not loose_files:
            return "仁哥，雲端硬碟根目錄沒有散檔，已經很整齊了 ✨"

        # 2. AI 分析產生計畫
        logger.info(f"🤖 AI 分析中... ({len(loose_files)} 個散檔, {len(folders)} 個資料夾)")
        plan = self.llm.analyze_drive_for_organization(folders, loose_files)

        actions = plan.get("actions", [])
        summary = plan.get("summary", "")

        if not actions:
            return f"仁哥，Alice 檢查了根目錄的 {len(loose_files)} 個檔案，目前都分類得很好，不需要整理 👍"

        # 3. 暫存提案
        proposal = {
            "plan": plan,
            "loose_files": loose_files,
            "folders": folders,
            "created_at": time.time()
        }
        _pending_proposals[user_id] = proposal
        logger.info(f"📋 提案已暫存 (user={user_id}, {len(actions)} 項動作)")

        # 4. 格式化提案文字
        return self._format_proposal(loose_files, actions, summary)

    def confirm_and_execute(self, user_id: str) -> str:
        """
        執行已確認的整理提案。

        Returns:
            str: 執行報告
        """
        proposal = _pending_proposals.get(user_id)

        if not proposal:
            return "仁哥，目前沒有待確認的整理提案 😊"

        # 檢查是否過期
        if time.time() - proposal["created_at"] > PROPOSAL_TTL:
            del _pending_proposals[user_id]
            return "仁哥，上一個整理提案已過期（超過30分鐘）。需要的話可以再說「整理雲端硬碟」重新產生 😊"

        plan = proposal["plan"]
        actions = plan.get("actions", [])

        # 清除暫存（不管執行是否成功都清除，避免重複執行）
        del _pending_proposals[user_id]

        return self._execute_plan(actions, proposal["folders"])

    def cancel_proposal(self, user_id: str) -> str:
        """取消待確認的整理提案"""
        if user_id in _pending_proposals:
            del _pending_proposals[user_id]
            return "好的仁哥，已取消這次的整理計畫 👌"
        return "仁哥，目前沒有待確認的整理提案 😊"

    def has_pending_proposal(self, user_id: str) -> bool:
        """檢查是否有待確認的提案"""
        if user_id not in _pending_proposals:
            return False

        proposal = _pending_proposals[user_id]
        # 自動清除過期提案
        if time.time() - proposal["created_at"] > PROPOSAL_TTL:
            del _pending_proposals[user_id]
            return False

        return True

    def _format_proposal(self, loose_files: list, actions: list, summary: str) -> str:
        """格式化提案為 LINE 友善文字"""
        lines = ["📂 Alice 的雲端硬碟整理提案\n"]
        lines.append(f"掃描結果：根目錄有 {len(loose_files)} 個散檔\n")

        if summary:
            lines.append(f"💡 {summary}\n")

        lines.append("📋 整理計畫：")

        # 按目標資料夾分組
        folder_groups = {}
        new_folders = set()

        for action in actions:
            if action["type"] == "create_folder":
                new_folders.add(action["folder_name"])
            elif action["type"] == "move":
                target = action.get("target_folder", "未知")
                if target not in folder_groups:
                    folder_groups[target] = []
                folder_groups[target].append(action["file_name"])

        step = 1
        total_moves = 0
        total_new_folders = 0

        for folder_name, files in folder_groups.items():
            is_new = folder_name in new_folders
            prefix = "🆕 建立" if is_new else "📁 移入"
            if is_new:
                total_new_folders += 1

            lines.append(f"\n{step}. {prefix}「{folder_name}」")
            for f in files:
                lines.append(f"   → {f}")
                total_moves += 1
            step += 1

        lines.append(f"\n共計：{'建立 ' + str(total_new_folders) + ' 個新資料夾、' if total_new_folders > 0 else ''}移動 {total_moves} 個檔案")
        lines.append("\n✅ 回覆「好」或「執行」→ Alice 立即執行")
        lines.append("❌ 回覆「不要」或「取消」→ 放棄此次整理")
        lines.append("⏰ 30 分鐘內未回覆將自動取消")

        return "\n".join(lines)

    def _execute_plan(self, actions: list, existing_folders: list) -> str:
        """
        執行整理計畫。

        Returns:
            str: 執行報告
        """
        logger.info(f"🚀 開始執行 Drive 整理：{len(actions)} 項動作")

        # 建立「既有資料夾名→ID」對照表
        folder_map = {f["name"]: f["id"] for f in existing_folders}

        # 統計
        folders_created = 0
        files_moved = 0
        errors = []

        # 先建立所有需要的新資料夾
        for action in actions:
            if action["type"] == "create_folder":
                folder_name = action["folder_name"]
                if folder_name not in folder_map:
                    folder_id = self.drive.create_folder(folder_name)
                    if folder_id:
                        folder_map[folder_name] = folder_id
                        folders_created += 1
                    else:
                        errors.append(f"建立資料夾「{folder_name}」失敗")

        # 再移動檔案
        for action in actions:
            if action["type"] == "move":
                file_id = action.get("file_id")
                file_name = action.get("file_name", "未知檔案")
                target_folder = action.get("target_folder", "")

                target_id = folder_map.get(target_folder)
                if not target_id:
                    errors.append(f"「{file_name}」→ 找不到「{target_folder}」")
                    continue

                if self.drive.move_file(file_id, target_id):
                    files_moved += 1
                else:
                    errors.append(f"「{file_name}」移動失敗")

        # 產生報告
        report_lines = ["✅ Alice Drive 整理報告\n"]
        report_lines.append(f"📁 建立 {folders_created} 個新資料夾")
        report_lines.append(f"📦 移動 {files_moved} 個檔案")

        if errors:
            report_lines.append(f"\n⚠️ {len(errors)} 個問題：")
            for err in errors[:5]:  # 最多列 5 個錯誤
                report_lines.append(f"  • {err}")

        report_lines.append(f"\n整理完成！仁哥的雲端硬碟現在更整齊了 ✨")

        result = "\n".join(report_lines)
        logger.info(f"🏁 Drive 整理完成: {folders_created} 資料夾, {files_moved} 移動, {len(errors)} 錯誤")
        return result
