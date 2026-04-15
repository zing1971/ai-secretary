"""tests/test_main.py — main.py 純函數單元測試"""
import os
import tempfile
from unittest.mock import patch, MagicMock


def test_parse_cloudflare_url_found():
    """cloudflared 輸出行含 URL 時應解析並回傳"""
    from main import parse_cloudflare_url

    line = "INF +----------------------------+ https://abc-def-123.trycloudflare.com"
    assert parse_cloudflare_url(line) == "https://abc-def-123.trycloudflare.com"


def test_parse_cloudflare_url_not_found():
    """不含 URL 的行應回傳 None"""
    from main import parse_cloudflare_url

    assert parse_cloudflare_url("INF Starting tunnel connection") is None


def test_register_webhook_success():
    """Telegram 回傳 ok:true 時應回傳 True"""
    from main import register_webhook

    mock_resp = MagicMock()
    mock_resp.json.return_value = {"ok": True}

    with patch("main.requests.post", return_value=mock_resp):
        assert register_webhook("fake-token", "https://abc.trycloudflare.com") is True


def test_register_webhook_failure():
    """Telegram 回傳 ok:false 時應回傳 False（max_retries=1 避免延遲）"""
    from main import register_webhook

    mock_resp = MagicMock()
    mock_resp.json.return_value = {"ok": False, "description": "Bad Request"}

    with patch("main.requests.post", return_value=mock_resp), patch("main.time.sleep"):
        assert register_webhook("fake-token", "https://abc.trycloudflare.com", max_retries=1) is False


def test_register_webhook_exception():
    """requests 拋出例外時應回傳 False 而非崩潰"""
    from main import register_webhook

    with patch("main.requests.post", side_effect=ConnectionError("timeout")), patch("main.time.sleep"):
        assert register_webhook("fake-token", "https://abc.trycloudflare.com", max_retries=1) is False


def test_register_webhook_retries_then_succeeds():
    """第一次失敗後重試成功應回傳 True"""
    from main import register_webhook

    fail_resp = MagicMock()
    fail_resp.json.return_value = {"ok": False, "description": "Failed to resolve host"}
    ok_resp = MagicMock()
    ok_resp.json.return_value = {"ok": True}

    with patch("main.requests.post", side_effect=[fail_resp, ok_resp]), patch("main.time.sleep"):
        assert register_webhook("fake-token", "https://abc.trycloudflare.com", max_retries=2) is True


def test_update_hermes_webhook_url():
    """update_hermes_webhook_url 應正確替換 config.yaml 中的 webhook_url"""
    from main import update_hermes_webhook_url

    original = 'webhook_url: "https://placeholder.trycloudflare.com"\n'
    expected = 'webhook_url: "https://new-tunnel.trycloudflare.com/webhook"\n'

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(original)
        tmp_path = f.name

    try:
        with patch("main.os.path.expanduser", return_value=tmp_path):
            update_hermes_webhook_url("https://new-tunnel.trycloudflare.com")
        with open(tmp_path) as f:
            assert f.read() == expected
    finally:
        os.unlink(tmp_path)


def test_start_cloudflared_returns_url():
    """cloudflared 輸出含 URL 的行時，應回傳 (proc, url)"""
    import io

    mock_proc = MagicMock()
    mock_proc.stdout = iter([
        "INF Starting tunnel\n",
        "INF +----------------------------+ https://test-123.trycloudflare.com\n",
    ])

    with patch("main.subprocess.Popen", return_value=mock_proc):
        from main import start_cloudflared
        proc, url = start_cloudflared(8080)

    assert url == "https://test-123.trycloudflare.com"
    assert proc is mock_proc


def test_start_cloudflared_raises_on_early_exit():
    """cloudflared stdout 關閉前未輸出 URL 時，應拋出 RuntimeError"""
    import pytest

    mock_proc = MagicMock()
    mock_proc.stdout = iter(["INF Starting tunnel\n"])  # no URL line
    mock_proc.returncode = 1

    with patch("main.subprocess.Popen", return_value=mock_proc):
        from main import start_cloudflared
        with pytest.raises(RuntimeError, match="cloudflared 異常結束"):
            start_cloudflared(8080)
