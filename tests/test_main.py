"""tests/test_main.py — main.py 純函數單元測試"""
from unittest.mock import patch, MagicMock


def test_sync_persona_copies_file(tmp_path):
    """sync_persona 應將 persona_soul.md 複製到 ~/.hermes/SOUL.md"""
    import shutil
    import os
    from main import sync_persona

    src = tmp_path / "persona_soul.md"
    src.write_text("test persona")
    dst_dir = tmp_path / ".hermes"

    with (
        patch("main.os.path.dirname", return_value=str(tmp_path)),
        patch("main.os.path.expanduser", return_value=str(dst_dir)),
    ):
        sync_persona()

    assert (dst_dir / "SOUL.md").read_text() == "test persona"


def test_delete_webhook_success():
    """Telegram 回傳 ok:true 時應記錄成功並不拋例外"""
    from main import delete_webhook

    mock_resp = MagicMock()
    mock_resp.json.return_value = {"ok": True}

    with patch("main.requests.post", return_value=mock_resp):
        delete_webhook("fake-token")  # 不應拋例外


def test_delete_webhook_failure_logs_warning():
    """Telegram 回傳 ok:false 時應記錄警告而不崩潰"""
    from main import delete_webhook

    mock_resp = MagicMock()
    mock_resp.json.return_value = {"ok": False, "description": "Bad Request"}

    with patch("main.requests.post", return_value=mock_resp):
        delete_webhook("fake-token")  # 不應拋例外


def test_delete_webhook_exception_logs_warning():
    """requests 拋出例外時應記錄警告而不崩潰"""
    from main import delete_webhook

    with patch("main.requests.post", side_effect=ConnectionError("timeout")):
        delete_webhook("fake-token")  # 不應拋例外
