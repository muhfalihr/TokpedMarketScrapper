"""Tests for the CLI."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from laptop_market_scraper.cli import app

runner = CliRunner()


def test_crawl_command_exists():
    result = runner.invoke(app, ["crawl", "--help"])

    assert result.exit_code == 0
    assert "--crawl-dir" in result.stdout
    assert "--max-items" in result.stdout
    assert "--browser-fallback" in result.stdout


def test_inspect_listing_help():
    result = runner.invoke(app, ["inspect-listing", "--help"])

    assert result.exit_code == 0
    assert "target" in result.stdout.lower()
    assert "url or path to html file" in result.stdout.lower()


def test_inspect_listing_local_state_fixture():
    fixture_path = Path("tests/fixtures/tokopedia_search_state.html")
    result = runner.invoke(app, ["inspect-listing", str(fixture_path)])

    assert result.exit_code == 0
    assert "Source: File read:" in result.stdout
    assert "Body size:" in result.stdout
    assert "Scripts summary:" in result.stdout
    assert "Detected hydration markers: __NEXT_DATA__" in result.stdout
    assert "State candidates found: 1" in result.stdout
    assert "Selected state source: __NEXT_DATA__" in result.stdout
    assert "Product count: 3" in result.stdout
    assert "current_page=1" in result.stdout
    assert "next_page=2" in result.stdout
    assert "has_next_page=True" in result.stdout
    assert "total_products=1200" in result.stdout
    assert "DOM fallback used: no" in result.stdout
    assert "flight_detected=no" in result.stdout


def test_inspect_listing_local_raw_state_fixture():
    fixture_path = Path("tests/fixtures/tokopedia_search_raw.html")
    result = runner.invoke(app, ["inspect-listing", str(fixture_path)])

    assert result.exit_code == 0
    assert "Detected hydration markers: __INITIAL_STATE__" in result.stdout
    assert "Selected state source: window.__INITIAL_STATE__" in result.stdout
    assert "Product count: 2" in result.stdout
    assert "current_page=2" in result.stdout
    assert "next_page=3" in result.stdout
    assert "has_next_page=True" in result.stdout
    assert "total_products=480" in result.stdout
    assert "DOM fallback used: no" in result.stdout


def test_inspect_listing_local_dom_fixture():
    fixture_path = Path("tests/fixtures/listing_page.html")
    result = runner.invoke(app, ["inspect-listing", str(fixture_path)])

    assert result.exit_code == 0
    assert "Product count: 2" in result.stdout
    assert "DOM fallback used: yes" in result.stdout
    assert "Selected state source: None" in result.stdout


def test_inspect_listing_mocked_http_url():
    fixture_path = Path("tests/fixtures/tokopedia_search_state.html")
    content_bytes = fixture_path.read_bytes()
    content_str = content_bytes.decode("utf-8")

    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.url = "https://www.tokopedia.com/search?q=laptop"
    mock_resp.body = content_bytes
    mock_resp.text = content_str

    with patch("laptop_market_scraper.cli.Fetcher.get", return_value=mock_resp) as mock_get:
        result = runner.invoke(app, ["inspect-listing", "https://www.tokopedia.com/search?q=laptop"])

        assert result.exit_code == 0
        mock_get.assert_called_once_with("https://www.tokopedia.com/search?q=laptop")
        assert "Source: HTTP 200 (https://www.tokopedia.com/search?q=laptop)" in result.stdout
        assert "Selected state source: __NEXT_DATA__" in result.stdout
        assert "Product count: 3" in result.stdout
        assert "DOM fallback used: no" in result.stdout


def test_inspect_listing_nonexistent_file():
    result = runner.invoke(app, ["inspect-listing", "nonexistent_file_99999.html"])

    assert result.exit_code == 1
    assert "File not found" in result.output


def test_inspect_listing_http_fetch_error():
    with patch(
        "laptop_market_scraper.cli.Fetcher.get",
        side_effect=RuntimeError("Connection refused by server"),
    ):
        result = runner.invoke(app, ["inspect-listing", "https://www.tokopedia.com/search?q=laptop"])

        assert result.exit_code == 1
        assert "Error fetching URL" in result.output


def test_inspect_listing_flight_marker_detected(tmp_path):
    flight_html = """
    <html>
        <head>
            <script>self.__next_f.push([1, "1:HL[\\"link\\"]"])</script>
        </head>
        <body>
            <a href="https://www.tokopedia.com/shop/laptop-1">Laptop 1</a>
        </body>
    </html>
    """
    file_path = tmp_path / "flight_sample.html"
    file_path.write_text(flight_html, encoding="utf-8")

    result = runner.invoke(app, ["inspect-listing", str(file_path)])

    assert result.exit_code == 0
    assert "__next_f" in result.stdout
    assert "flight_detected=yes" in result.stdout
    assert "DOM fallback used: yes" in result.stdout
    assert "Product count: 1" in result.stdout


def test_inspect_listing_json_decode_error(tmp_path):
    bad_json_html = """
    <html>
        <head>
            <script id="__NEXT_DATA__" type="application/json">{ invalid json here }</script>
        </head>
        <body>
            <a href="https://www.tokopedia.com/shop/laptop-2">Laptop 2</a>
        </body>
    </html>
    """
    file_path = tmp_path / "bad_json.html"
    file_path.write_text(bad_json_html, encoding="utf-8")

    result = runner.invoke(app, ["inspect-listing", str(file_path)])

    assert result.exit_code == 0
    assert "json_errors=1" in result.stdout
    assert "DOM fallback used: yes" in result.stdout

