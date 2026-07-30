"""Bounded parser for the public Butian AI Security RSS feed.

RSS text is display-only, remains explicitly untrusted, and is never promoted to
model context by this module. Project control mappings are local keyword rules.
"""
from __future__ import annotations

import html
import re
import unicodedata
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Callable
from urllib.parse import unquote, urlsplit


AISECURITY_RSS_URL = "https://forum.butian.net/Rss/ai-security"
AISECURITY_SOURCE_NAME = "Butian AI Security"
MAX_RSS_BYTES = 256 * 1024
MAX_RSS_ITEMS = 40
MAX_XML_ELEMENTS = 1200
MAX_XML_DEPTH = 12
MAX_TITLE_CHARS = 240
MAX_DESCRIPTION_CHARS = 1200
MAX_DATE_CHARS = 64

_SNAPSHOT_PATH = Path(__file__).parent / "snapshots" / "aisecurity.xml"
_ARTICLE_PATH = re.compile(r"/ai_security/([1-9][0-9]{0,11})")
_BLOCKED_HTML_ELEMENTS = {"script", "style", "template", "noscript", "iframe", "object"}
_BREAK_HTML_ELEMENTS = {
    "br",
    "div",
    "p",
    "li",
    "tr",
    "td",
    "th",
    "section",
    "article",
    "header",
    "footer",
}

_CONTROL_MAPPING_RULES = (
    (
        "prompt-and-unicode",
        ("提示词", "prompt", "unicode", "不可见", "注入", "injection", "越狱"),
        (
            "guardrail.unicode_normalization",
            "guardrail.prompt_injection_rules",
            "security_benchmark.prompt_regression",
        ),
    ),
    (
        "agent-tool-boundary",
        ("mcp", "agent", "智能体", "工具投毒", "tool", "越权", "链式滥用"),
        (
            "tool_registry.schema_allowlist",
            "guardrail.tool_output_scan",
            "audit.trace",
        ),
    ),
    (
        "supply-chain",
        ("供应链", "依赖", "checkpoint", "反序列化", "cve", "skill"),
        (
            "security.external_result_review",
            "security.protected_path_rules",
        ),
    ),
    (
        "network-and-credentials",
        ("ssrf", "凭据", "密钥", "云账户", "外带", "exfiltration", "credential"),
        (
            "guardrail.protected_credential_rules",
            "executor.command_allowlist",
            "audit.redaction",
        ),
    ),
    (
        "authorized-testing",
        ("渗透", "红队", "漏洞", "rce", "攻击", "靶场", "bypass"),
        (
            "security.authorized_scope_gate",
            "security.external_result_review",
        ),
    ),
    (
        "blue-team-operations",
        ("soc", "蓝队", "日志", "威胁", "告警", "检测", "响应"),
        (
            "monitoring.read_only_evidence",
            "audit.trace",
        ),
    ),
)


class FeedSecurityError(ValueError):
    """Raised when RSS input violates a fixed source or parser boundary."""


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._suppressed_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del attrs
        normalized = tag.lower()
        if normalized in _BLOCKED_HTML_ELEMENTS:
            self._suppressed_depth += 1
        elif not self._suppressed_depth and normalized in _BREAK_HTML_ELEMENTS:
            self.parts.append(" ")

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del attrs
        if not self._suppressed_depth and tag.lower() in _BREAK_HTML_ELEMENTS:
            self.parts.append(" ")

    def handle_endtag(self, tag: str) -> None:
        normalized = tag.lower()
        if normalized in _BLOCKED_HTML_ELEMENTS and self._suppressed_depth:
            self._suppressed_depth -= 1
        elif not self._suppressed_depth and normalized in _BREAK_HTML_ELEMENTS:
            self.parts.append(" ")

    def handle_data(self, data: str) -> None:
        if not self._suppressed_depth:
            self.parts.append(data)


class _RejectRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: Any,
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> None:
        del req, fp, code, msg, headers, newurl
        raise urllib.error.URLError("RSS redirects are not allowed")


def load_aisecurity_feed(
    url: str = AISECURITY_RSS_URL,
    *,
    timeout_seconds: float = 5.0,
    fetcher: Callable[[str, float], bytes | str] | None = None,
) -> dict[str, Any]:
    """Fetch the one allowlisted feed, falling back to a bundled snapshot.

    The injectable fetcher exists for deterministic tests. It cannot override
    the allowlisted URL.
    """
    if url != AISECURITY_RSS_URL:
        raise FeedSecurityError("AISecurity RSS URL is not allowlisted")
    if not 0.1 <= float(timeout_seconds) <= 30.0:
        raise FeedSecurityError("RSS timeout must be between 0.1 and 30 seconds")

    transport = fetcher or _fetch_rss_bytes
    try:
        payload = transport(AISECURITY_RSS_URL, float(timeout_seconds))
        parsed = parse_aisecurity_rss(payload)
    except (OSError, TimeoutError, urllib.error.URLError, FeedSecurityError):
        return load_aisecurity_snapshot()

    parsed["delivery"] = "network"
    parsed["snapshot_used"] = False
    return parsed


def load_aisecurity_snapshot() -> dict[str, Any]:
    """Return the bundled reviewed snapshot without making a network request."""
    parsed = parse_aisecurity_rss(_SNAPSHOT_PATH.read_bytes())
    parsed["delivery"] = "local_snapshot"
    parsed["snapshot_used"] = True
    return parsed


def parse_aisecurity_rss(payload: bytes | str) -> dict[str, Any]:
    """Parse and sanitize an AISecurity RSS payload without network access."""
    raw = _bounded_payload(payload)
    try:
        decoded = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise FeedSecurityError("AISecurity RSS must use UTF-8 encoding") from exc
    if re.search(r"<!\s*(?:DOCTYPE|ENTITY)\b", decoded, flags=re.IGNORECASE):
        raise FeedSecurityError("DTD and entity declarations are not allowed in RSS")
    try:
        root = ET.fromstring(decoded)
    except (ET.ParseError, RecursionError, ValueError) as exc:
        raise FeedSecurityError("invalid AISecurity RSS XML") from exc
    _validate_xml_tree(root)

    channel = next((node for node in root.iter() if _local_name(node.tag) == "channel"), None)
    if channel is None:
        raise FeedSecurityError("AISecurity RSS channel is missing")
    item_nodes = [node for node in list(channel) if _local_name(node.tag) == "item"]
    if len(item_nodes) > MAX_RSS_ITEMS:
        raise FeedSecurityError("AISecurity RSS item limit exceeded")

    items = [_parse_item(node) for node in item_nodes]
    return {
        "source": {
            "name": AISECURITY_SOURCE_NAME,
            "feed_url": AISECURITY_RSS_URL,
        },
        "untrusted": True,
        "automatic_model_ingestion": False,
        "mapping_mode": "deterministic_local_keywords",
        "item_count": len(items),
        "items": items,
    }


def _fetch_rss_bytes(url: str, timeout_seconds: float) -> bytes:
    if url != AISECURITY_RSS_URL:
        raise FeedSecurityError("AISecurity RSS URL is not allowlisted")
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/rss+xml, application/xml, text/xml",
            "User-Agent": "SafeOpsAgent-security-intel/1.0",
        },
        method="GET",
    )
    opener = urllib.request.build_opener(_RejectRedirects())
    with opener.open(request, timeout=timeout_seconds) as response:
        if response.geturl() != AISECURITY_RSS_URL:
            raise FeedSecurityError("AISecurity RSS response changed origin")
        data = response.read(MAX_RSS_BYTES + 1)
    if len(data) > MAX_RSS_BYTES:
        raise FeedSecurityError("AISecurity RSS exceeds its size limit")
    return data


def _bounded_payload(payload: bytes | str) -> bytes:
    if isinstance(payload, str):
        try:
            raw = payload.encode("utf-8")
        except UnicodeEncodeError as exc:
            raise FeedSecurityError("RSS text is not valid UTF-8") from exc
    elif isinstance(payload, bytes):
        raw = payload
    else:
        raise FeedSecurityError("RSS payload must be bytes or text")
    if not raw or len(raw) > MAX_RSS_BYTES:
        raise FeedSecurityError("RSS payload is empty or exceeds its size limit")
    return raw


def _validate_xml_tree(root: ET.Element) -> None:
    elements = 0
    stack = [(root, 1)]
    while stack:
        node, depth = stack.pop()
        elements += 1
        if elements > MAX_XML_ELEMENTS:
            raise FeedSecurityError("AISecurity RSS XML element limit exceeded")
        if depth > MAX_XML_DEPTH:
            raise FeedSecurityError("AISecurity RSS XML depth limit exceeded")
        stack.extend((child, depth + 1) for child in list(node))


def _parse_item(node: ET.Element) -> dict[str, Any]:
    title = _clean_text(_child_text(node, "title"), MAX_TITLE_CHARS)
    description = _clean_text(_child_text(node, "description"), MAX_DESCRIPTION_CHARS)
    published_at = _clean_text(_child_text(node, "pubDate"), MAX_DATE_CHARS)
    article_url = _canonical_article_url(_child_text(node, "guid") or _child_text(node, "link"))
    mappings, controls = _map_project_controls(f"{title} {description}")
    return {
        "title": title,
        "description": description,
        "published_at": published_at,
        "article_url": article_url,
        "source": AISECURITY_SOURCE_NAME,
        "source_feed": AISECURITY_RSS_URL,
        "untrusted": True,
        "automatic_model_ingestion": False,
        "mapping_rules": mappings,
        "project_controls": controls,
    }


def _child_text(node: ET.Element, child_name: str) -> str:
    child = next((item for item in list(node) if _local_name(item.tag) == child_name), None)
    if child is None:
        return ""
    return "".join(child.itertext())


def _local_name(tag: Any) -> str:
    value = str(tag)
    return value.rsplit("}", 1)[-1]


def _clean_text(value: str, limit: int) -> str:
    normalized = unicodedata.normalize("NFKC", value or "")
    for _ in range(2):
        decoded = html.unescape(normalized)
        if decoded == normalized:
            break
        normalized = decoded
    normalized = "".join(_safe_character(char) for char in normalized)
    parser = _TextExtractor()
    try:
        parser.feed(normalized)
        parser.close()
        text = "".join(parser.parts)
    except Exception as exc:
        raise FeedSecurityError("RSS HTML fragment could not be sanitized") from exc
    text = "".join(_safe_character(char) for char in unicodedata.normalize("NFKC", text))
    text = " ".join(text.split())
    return text[:limit]


def _safe_character(char: str) -> str:
    category = unicodedata.category(char)
    if category in {"Cc", "Cf", "Cs"}:
        return " " if char.isspace() else ""
    return char


def _canonical_article_url(value: str) -> str:
    cleaned = _clean_text(value, 512)
    try:
        parts = urlsplit(cleaned)
        port = parts.port
    except ValueError:
        return ""
    if parts.scheme != "https" or parts.netloc.lower() != "forum.butian.net":
        return ""
    if parts.query or parts.fragment or parts.username or parts.password or port:
        return ""
    match = _ARTICLE_PATH.fullmatch(unquote(parts.path))
    if not match:
        return ""
    return f"https://forum.butian.net/ai_security/{match.group(1)}"


def _map_project_controls(text: str) -> tuple[list[str], list[str]]:
    normalized = unicodedata.normalize("NFKC", text).casefold()
    mapping_ids: list[str] = []
    controls: list[str] = ["security.external_content_review"]
    for rule_id, keywords, mapped_controls in _CONTROL_MAPPING_RULES:
        if any(keyword.casefold() in normalized for keyword in keywords):
            mapping_ids.append(rule_id)
            for control in mapped_controls:
                if control not in controls:
                    controls.append(control)
    return mapping_ids, controls
