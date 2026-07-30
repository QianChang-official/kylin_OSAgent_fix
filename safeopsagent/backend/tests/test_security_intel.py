from __future__ import annotations

import pytest

from backend.security_intel import (
    AISECURITY_RSS_URL,
    FeedSecurityError,
    load_aisecurity_feed,
    load_integration_catalog,
    parse_aisecurity_rss,
)


def test_catalog_pins_external_only_integrations_and_governance():
    catalog = load_integration_catalog()
    integrations = {item["id"]: item for item in catalog["integrations"]}

    codex = integrations["openai-codex-security"]
    assert codex["pinned_version"] == "0.1.4"
    assert codex["license"] == "Apache-2.0"
    assert codex["integration_mode"] == "external_results_only"
    assert codex["runtime_execution"] is False
    assert codex["loongarch_runtime_compatible"] is False

    skillguard = integrations["skillguard-cli"]
    assert skillguard["pinned_version"] == "0.1.0"
    assert skillguard["license"] == "MIT"
    assert skillguard["integration_mode"] == "ci_only"
    assert skillguard["version_pin_required"] is True

    governance = catalog["butian_ai_tools_governance"]
    assert governance["automatic_full_site_scraping"] == "prohibited"
    assert governance["active_attack_categories"] == "defensive_reference_only"
    assert catalog["external_content_policy"]["automatic_model_ingestion"] is False


def test_rss_parser_strips_html_controls_zero_width_and_bidi():
    long_title = "A" * 260
    long_description = "B" * 1300
    payload = f"""<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0"><channel><item>
      <guid>https://evil.example/ai_security/1</guid>
      <title><![CDATA[M\u200bCP \u202ePrompt <b>Unicode</b><script>IGNORE PREVIOUS</script>{long_title}]]></title>
      <description><![CDATA[SSRF\u2066\n<div>defense</div><style>steal secrets</style>{long_description}]]></description>
      <pubDate>2026-07-30\t09:00:00</pubDate>
    </item></channel></rss>"""

    result = parse_aisecurity_rss(payload)
    item = result["items"][0]

    assert result["untrusted"] is True
    assert result["automatic_model_ingestion"] is False
    assert item["article_url"] == ""
    assert "<" not in item["title"] and ">" not in item["title"]
    assert "IGNORE PREVIOUS" not in item["title"]
    assert "steal secrets" not in item["description"]
    assert all(token not in item["title"] + item["description"] for token in ("\u200b", "\u202e", "\u2066"))
    assert "\n" not in item["description"] and "\t" not in item["published_at"]
    assert len(item["title"]) <= 240
    assert len(item["description"]) <= 1200
    assert item["mapping_rules"] == [
        "prompt-and-unicode",
        "agent-tool-boundary",
        "network-and-credentials",
    ]
    assert "tool_registry.schema_allowlist" in item["project_controls"]
    assert "executor.command_allowlist" in item["project_controls"]


def test_rss_loader_rejects_other_urls_without_calling_fetcher():
    called = False

    def fetcher(url: str, timeout: float) -> bytes:
        nonlocal called
        called = True
        return b""

    with pytest.raises(FeedSecurityError, match="not allowlisted"):
        load_aisecurity_feed("https://example.com/feed", fetcher=fetcher)
    assert called is False


def test_rss_loader_uses_small_local_snapshot_on_network_failure():
    def unavailable(url: str, timeout: float) -> bytes:
        assert url == AISECURITY_RSS_URL
        assert timeout == 1.0
        raise OSError("offline")

    result = load_aisecurity_feed(timeout_seconds=1.0, fetcher=unavailable)

    assert result["delivery"] == "local_snapshot"
    assert result["snapshot_used"] is True
    assert 1 <= result["item_count"] <= 5
    assert all(item["untrusted"] is True for item in result["items"])


def test_rss_parser_rejects_entity_declarations():
    payload = """<?xml version="1.0"?>
    <!DOCTYPE rss [<!ENTITY x "injected">]>
    <rss version="2.0"><channel><item><title>&x;</title></item></channel></rss>"""

    with pytest.raises(FeedSecurityError, match="entity declarations"):
        parse_aisecurity_rss(payload)
