"""tests/test_main.py — main.py 純函數單元測試"""
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
    """Telegram 回傳 ok:false 時應回傳 False"""
    from main import register_webhook

    mock_resp = MagicMock()
    mock_resp.json.return_value = {"ok": False, "description": "Bad Request"}

    with patch("main.requests.post", return_value=mock_resp):
        assert register_webhook("fake-token", "https://abc.trycloudflare.com") is False


def test_register_webhook_exception():
    """requests 拋出例外時應回傳 False 而非崩潰"""
    from main import register_webhook

    with patch("main.requests.post", side_effect=ConnectionError("timeout")):
        assert register_webhook("fake-token", "https://abc.trycloudflare.com") is False
