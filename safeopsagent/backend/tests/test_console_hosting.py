import re

from fastapi.testclient import TestClient

from backend.app import CONSOLE_DIST_DIR, app


client = TestClient(app)


def test_console_build_is_present():
    assert (CONSOLE_DIST_DIR / "index.html").is_file()


def test_console_root_and_nested_routes_return_spa():
    root = client.get("/console/")
    nested = client.get("/console/audit")

    assert root.status_code == 200
    assert nested.status_code == 200
    assert "SafeOpsAgent" in root.text
    assert nested.text == root.text
    assert root.headers["cache-control"] == "no-cache"


def test_console_hashed_asset_is_served():
    index = client.get("/console/")
    match = re.search(r'src="(/console/assets/[^"]+\.js)"', index.text)

    assert match is not None
    asset = client.get(match.group(1))
    assert asset.status_code == 200
    assert "javascript" in asset.headers.get("content-type", "")
    assert "immutable" in asset.headers.get("cache-control", "")


def test_console_fallback_does_not_swallow_backend_api():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert "text/html" not in response.headers.get("content-type", "")
