"""Read the local, auditable third-party integration manifest."""
from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

_CATALOG_PATH = Path(__file__).with_name("integration_catalog.json")
_MAX_CATALOG_BYTES = 32 * 1024


def load_integration_catalog() -> dict[str, Any]:
    """Return an isolated copy of the reviewed local integration catalog."""
    payload = _CATALOG_PATH.read_bytes()
    if len(payload) > _MAX_CATALOG_BYTES:
        raise ValueError("security integration catalog exceeds its size limit")
    catalog = json.loads(payload.decode("utf-8"))
    if not isinstance(catalog, dict) or catalog.get("schema_version") != 1:
        raise ValueError("unsupported security integration catalog")
    integrations = catalog.get("integrations")
    if not isinstance(integrations, list) or not integrations:
        raise ValueError("security integration catalog has no integrations")
    return deepcopy(catalog)
