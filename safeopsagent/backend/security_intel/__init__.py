"""Defensive, read-only integrations for external security intelligence."""
from .catalog import load_integration_catalog
from .rss import (
    AISECURITY_RSS_URL,
    FeedSecurityError,
    load_aisecurity_feed,
    load_aisecurity_snapshot,
    parse_aisecurity_rss,
)

__all__ = [
    "AISECURITY_RSS_URL",
    "FeedSecurityError",
    "load_aisecurity_feed",
    "load_aisecurity_snapshot",
    "load_integration_catalog",
    "parse_aisecurity_rss",
]
