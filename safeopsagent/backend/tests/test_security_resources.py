from fastapi.testclient import TestClient

from backend.app import app


client = TestClient(app)


def test_security_resources_include_external_sources_and_mappings():
    response = client.get("/security/resources")
    body = response.json()

    assert response.status_code == 200
    assert body["codex_security"]["package"] == "@openai/codex-security"
    assert body["codex_security"]["pinned_version"] == "0.1.4"
    assert all("npx" not in command for command in body["codex_security"]["commands"])
    assert any(source["url"] == "https://forum.butian.net/AITools" for source in body["sources"])
    assert any(source["url"] == "https://forum.butian.net/AISecurity" for source in body["sources"])
    assert len(body["tool_categories"]) >= 20
    assert len(body["articles"]) >= 10
    assert body["policy"]["restricted_category_count"] > 0
