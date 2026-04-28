"""
Alice Tools - CLI wrapper for AI Secretary Google Workspace skills.

Alice 使用 terminal 工具呼叫此腳本，以存取所有 Google Workspace 功能。

Usage:
  alice calendar list
  alice calendar range --from YYYY-MM-DD --to YYYY-MM-DD
  alice calendar create --title T --start "YYYY-MM-DD HH:MM" --end "YYYY-MM-DD HH:MM" [--desc D] [--location L]
  alice calendar update --id ID [--title T] [--start S] [--end E] [--desc D] [--location L]
  alice calendar delete --id ID
  alice gmail search [--query Q] [--max N]
  alice gmail read --id MSG_ID
  alice gmail draft --to EMAIL --subject S --body B [--thread T]
  alice gmail send --draft-id ID
  alice gmail reply --thread T --to EMAIL --subject S --body B
  alice tasks list
  alice tasks add --title T [--notes N] [--due "RFC3339"]
  alice tasks done --id ID
  alice drive search --keyword K [--max N]
  alice contacts search --query Q [--max N]
  alice contacts create --name N --email E [--phone P] [--company C] [--title T] [--label L]
  alice generate --task T [--context C]
  alice memory remember --topic T --content C
  alice memory recall [--query Q]
  alice memory forget --topic T
  alice vision --url URL [--prompt P]
  alice vision --file PATH [--prompt P]
"""

import os
import sys
import argparse

# ── Path setup ────────────────────────────────────────────────────────────────
_BIN_DIR = os.path.dirname(os.path.abspath(__file__))
_APP_DIR = os.path.dirname(_BIN_DIR)
_SKILLS_DIR = os.path.join(_APP_DIR, "skills")

sys.path.insert(0, _APP_DIR)
sys.path.insert(0, _SKILLS_DIR)


def _load_dotenv() -> None:
    """Load .env when running outside systemd (e.g. local testing)."""
    env_file = os.path.join(_APP_DIR, ".env")
    if not os.path.exists(env_file):
        return
    with open(env_file, encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if key not in os.environ:
                os.environ[key] = val


_load_dotenv()


# ── Argument parser ──────────────────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="alice",
        description="Alice Tools – AI Secretary CLI",
    )
    sub = parser.add_subparsers(dest="domain")

    # ── calendar ──────────────────────────────────────────────────────────────
    cal = sub.add_parser("calendar", help="Google Calendar")
    cal_sub = cal.add_subparsers(dest="action")
    cal_sub.add_parser("list", help="今日行程")
    cc = cal_sub.add_parser("create", help="建立行程")
    cc.add_argument("--title", required=True)
    cc.add_argument("--start", required=True, metavar="DATETIME",
                    help='例："2026-04-20 10:00" 或 "2026-04-20"')
    cc.add_argument("--end", required=True, metavar="DATETIME")
    cc.add_argument("--desc", default=None, metavar="DESCRIPTION")
    cc.add_argument("--location", default=None)
    cr = cal_sub.add_parser("range", help="查詢日期範圍行程")
    cr.add_argument("--from", required=True, dest="from_date", metavar="YYYY-MM-DD")
    cr.add_argument("--to", required=True, dest="to_date", metavar="YYYY-MM-DD")
    cu = cal_sub.add_parser("update", help="更新行程")
    cu.add_argument("--id", required=True, dest="event_id")
    cu.add_argument("--title", default=None)
    cu.add_argument("--start", default=None, metavar="DATETIME")
    cu.add_argument("--end", default=None, metavar="DATETIME")
    cu.add_argument("--desc", default=None, metavar="DESCRIPTION")
    cu.add_argument("--location", default=None)
    cdel = cal_sub.add_parser("delete", help="刪除行程")
    cdel.add_argument("--id", required=True, dest="event_id")

    # ── gmail ─────────────────────────────────────────────────────────────────
    gm = sub.add_parser("gmail", help="Gmail")
    gm_sub = gm.add_subparsers(dest="action")
    gs = gm_sub.add_parser("search", help="搜尋信件")
    gs.add_argument("--query", default=None,
                    help='Gmail 搜尋語法，例 "is:unread from:boss@example.com"')
    gs.add_argument("--max", type=int, default=10, dest="max_results")
    gread = gm_sub.add_parser("read", help="讀取單封信件完整內容")
    gread.add_argument("--id", required=True, dest="msg_id", help="信件 ID")
    gd = gm_sub.add_parser("draft", help="建立草稿")
    gd.add_argument("--to", required=True, dest="to_email")
    gd.add_argument("--subject", required=True)
    gd.add_argument("--body", required=True, dest="body_text",
                    help="信件內文（純文字，換行用 \\n）")
    gd.add_argument("--thread", default=None, dest="thread_id",
                    help="回覆時的 threadId")
    gsend = gm_sub.add_parser("send", help="發送草稿")
    gsend.add_argument("--draft-id", required=True, dest="draft_id")
    greply = gm_sub.add_parser("reply", help="直接回覆信件")
    greply.add_argument("--thread", required=True, dest="thread_id")
    greply.add_argument("--to", required=True, dest="to_email")
    greply.add_argument("--subject", required=True)
    greply.add_argument("--body", required=True, dest="body_text",
                        help="回覆內文（純文字，換行用 \\n）")

    # ── tasks ─────────────────────────────────────────────────────────────────
    tk = sub.add_parser("tasks", help="Google Tasks")
    tk_sub = tk.add_subparsers(dest="action")
    tk_sub.add_parser("list", help="列出所有待辦")
    ta = tk_sub.add_parser("add", help="新增待辦")
    ta.add_argument("--title", required=True)
    ta.add_argument("--notes", default=None)
    ta.add_argument("--due", default=None,
                    help='RFC3339，例 "2026-05-01T23:59:59Z"')
    td = tk_sub.add_parser("done", help="標記任務完成")
    td.add_argument("--id", required=True, dest="task_id")

    # ── drive ─────────────────────────────────────────────────────────────────
    dr = sub.add_parser("drive", help="Google Drive")
    dr_sub = dr.add_subparsers(dest="action")
    ds = dr_sub.add_parser("search", help="搜尋檔案")
    ds.add_argument("--keyword", required=True)
    ds.add_argument("--max", type=int, default=5, dest="max_results")

    # ── contacts ──────────────────────────────────────────────────────────────
    ct = sub.add_parser("contacts", help="Google Contacts")
    ct_sub = ct.add_subparsers(dest="action")
    cts = ct_sub.add_parser("search", help="搜尋聯絡人")
    cts.add_argument("--query", required=True)
    cts.add_argument("--max", type=int, default=10, dest="max_results")
    ctc = ct_sub.add_parser("create", help="建立聯絡人")
    ctc.add_argument("--name", required=True)
    ctc.add_argument("--email", required=True)
    ctc.add_argument("--phone", default=None)
    ctc.add_argument("--company", default=None)
    ctc.add_argument("--title", default=None, dest="job_title")
    ctc.add_argument("--label", default=None,
                     help="可選：政府機關、學術研究、廠商代表、關鍵夥伴、媒體公關、其他")

    # ── generate ──────────────────────────────────────────────────────────────
    gen = sub.add_parser("generate",
                         help="使用 Gemini 2.5 Pro 起草高品質專業內容")
    gen.add_argument("--task", required=True,
                     help="任務描述，例：起草感謝信給王大明董事長")
    gen.add_argument("--context", default=None,
                     help="背景資訊（可選）：相關事實、參考資料等")

    # ── vision ────────────────────────────────────────────────────────────────
    vis = sub.add_parser(
        "vision",
        help="使用 Gemini 原生視覺分析圖片（名片掃描、圖片文字提取）",
    )
    vis_src = vis.add_mutually_exclusive_group(required=True)
    vis_src.add_argument("--url", default=None,
                         help="圖片 URL（支援 Telegram file URL、http/https）")
    vis_src.add_argument("--file", default=None, dest="image_file",
                         help="本地圖片檔案路徑")
    vis.add_argument(
        "--prompt",
        default=(
            "這是一張名片。請提取所有可見文字，並以以下格式整理："
            "姓名、職稱、公司、Email、電話、地址（如有）。"
            "若欄位不存在請標記 N/A。"
        ),
        help="給 Gemini 的分析提示（預設為名片提取）",
    )

    # ── memory ────────────────────────────────────────────────────────────────
    mem = sub.add_parser("memory", help="跨 session 長期記憶")
    mem_sub = mem.add_subparsers(dest="action")
    mr = mem_sub.add_parser("remember", help="儲存記憶")
    mr.add_argument("--topic", required=True,
                    help='記憶主題，例："仁哥行事曆偏好"')
    mr.add_argument("--content", required=True)
    mq = mem_sub.add_parser("recall", help="查詢記憶")
    mq.add_argument("--query", default=None)
    mf = mem_sub.add_parser("forget", help="刪除記憶")
    mf.add_argument("--topic", required=True)

    return parser


# ── Dispatch ──────────────────────────────────────────────────────────────────

def _dispatch(args: argparse.Namespace) -> str:
    d = args.domain

    if d == "calendar":
        from calendar_skills import (
            get_todays_calendar_events,
            create_calendar_event,
            get_calendar_events_range,
            update_calendar_event,
            delete_calendar_event,
        )
        if args.action == "list":
            return get_todays_calendar_events()
        if args.action == "create":
            return create_calendar_event(
                args.title, args.start, args.end, args.desc, args.location
            )
        if args.action == "range":
            return get_calendar_events_range(args.from_date, args.to_date)
        if args.action == "update":
            return update_calendar_event(
                args.event_id, args.title, args.start, args.end,
                args.desc, args.location,
            )
        if args.action == "delete":
            return delete_calendar_event(args.event_id)

    elif d == "gmail":
        from gmail_skills import (
            search_recent_gmails,
            read_email,
            create_email_draft,
            send_email_draft,
            reply_to_email,
        )
        if args.action == "search":
            return search_recent_gmails(args.query, args.max_results)
        if args.action == "read":
            return read_email(args.msg_id)
        if args.action == "draft":
            body = args.body_text.replace("\\n", "\n")
            return create_email_draft(
                args.to_email, args.subject, body, args.thread_id
            )
        if args.action == "send":
            return send_email_draft(args.draft_id)
        if args.action == "reply":
            body = args.body_text.replace("\\n", "\n")
            return reply_to_email(
                args.thread_id, args.to_email, args.subject, body
            )

    elif d == "tasks":
        from tasks_skills import add_google_task, list_google_tasks, complete_google_task
        if args.action == "list":
            return list_google_tasks()
        if args.action == "add":
            return add_google_task(args.title, args.notes, args.due)
        if args.action == "done":
            return complete_google_task(args.task_id)

    elif d == "drive":
        from drive_skills import search_drive_files
        if args.action == "search":
            return search_drive_files(args.keyword, args.max_results)

    elif d == "contacts":
        from contacts_skills import search_contacts, create_contact_entry
        if args.action == "search":
            return search_contacts(args.query, args.max_results)
        if args.action == "create":
            return create_contact_entry(
                args.name, args.email, args.phone,
                args.company, args.job_title, args.label,
            )

    elif d == "generate":
        from generation_skills import draft_professional_content
        return draft_professional_content(args.task, args.context)

    elif d == "vision":
        from generation_skills import analyze_image
        return analyze_image(
            image_url=args.url,
            image_file=args.image_file,
            prompt=args.prompt,
        )

    elif d == "memory":
        from memory_skills import remember, recall, forget
        if args.action == "remember":
            return remember(args.topic, args.content)
        if args.action == "recall":
            return recall(args.query)
        if args.action == "forget":
            return forget(args.topic)

    return ""


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    if not args.domain:
        parser.print_help()
        sys.exit(1)

    # Check sub-action where required
    needs_action = {"calendar", "gmail", "tasks", "drive", "contacts", "memory"}
    if args.domain in needs_action and not getattr(args, "action", None):
        # Print sub-parser help
        for action in parser._subparsers._actions:  # noqa: SLF001
            if hasattr(action, "_name_parser_map"):
                sub = action._name_parser_map.get(args.domain)  # noqa: SLF001
                if sub:
                    sub.print_help()
        sys.exit(1)

    try:
        result = _dispatch(args)
        if result:
            print(result)
    except RuntimeError as exc:
        print(f"❌ 錯誤：{exc}", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:  # noqa: BLE001
        print(f"❌ 系統錯誤：{type(exc).__name__}: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
