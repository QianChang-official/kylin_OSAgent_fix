# -*- coding: utf-8 -*-
"""从 Wikimedia Commons 抓取 CC-BY 协议的长城/故宫图片并压缩为控制台素材。

合规说明：仅采用 LicenseShortName 严格为 "CC BY"（含版本号，不含 SA/NC/ND）的图片，
并在输出目录生成 CREDITS 清单记录标题、作者、许可与来源页，满足 CC-BY 署名要求。

依赖：pillow；网络：urllib（标准库）。
"""
from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "frontend" / "vue-console" / "public" / "images"
API = "https://commons.wikimedia.org/w/api.php"
UA = "SafeOpsAgent-ThemeBot/1.0 (competition delivery; contact via repo issue)"
MIN_WIDTH = 1600
TARGET_WIDTH = 1920
JPEG_QUALITY = 82
MAX_RETRIES = 4

# (主题前缀, Commons 搜索词, 每主题张数) —— 文件名保持 greatwall-1/2、forbidden-city-3，CSS 引用无需改动
THEMES = [
    ("greatwall", "Great Wall of China filetype:bitmap", 2),
    ("forbidden-city", "Forbidden City filetype:bitmap", 1),
]

# 明确排除不适用的候选（内容与 UI 背景不符）
EXCLUDE_TITLES = {
    "File:Great wall child.jpg",  # 画面为游客/商贩群像
}


def http_get(url: str) -> bytes:
    """带 429 退避重试的 GET，遵守 Commons 限流要求。"""
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    for attempt in range(MAX_RETRIES):
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return resp.read()
        except urllib.error.HTTPError as exc:
            if exc.code == 429 and attempt < MAX_RETRIES - 1:
                delay = 15 * (attempt + 1)
                print(f"    429 限流，等待 {delay}s 后重试…")
                time.sleep(delay)
                continue
            raise
    raise RuntimeError("unreachable")


def api_query(params: dict) -> dict:
    url = API + "?" + urllib.parse.urlencode(params)
    return json.loads(http_get(url))


def search_ccby(query: str, limit: int = 40) -> list[dict]:
    """搜索并返回严格 CC-BY（非 SA/NC/ND）的图片元数据。"""
    data = api_query(
        {
            "action": "query", "format": "json", "generator": "search",
            "gsrsearch": query, "gsrnamespace": 6, "gsrlimit": str(limit),
            "prop": "imageinfo", "iiprop": "url|size|extmetadata", "iiurlwidth": str(TARGET_WIDTH),
        }
    )
    pages = data.get("query", {}).get("pages", {})
    results: list[dict] = []
    for page in pages.values():
        info = (page.get("imageinfo") or [{}])[0]
        meta = info.get("extmetadata", {})
        license_name = (meta.get("LicenseShortName", {}) or {}).get("value", "")
        if "CC BY" not in license_name or any(tag in license_name for tag in ("SA", "NC", "ND")):
            continue
        artist_html = (meta.get("Artist", {}) or {}).get("value", "")
        results.append(
            {
                "title": page.get("title", ""),
                "license": license_name,
                "artist": artist_html,
                "credit": (meta.get("Credit", {}) or {}).get("value", ""),
                "page": (meta.get("ObjectName", {}) or {}).get("value", ""),
                "description_url": info.get("descriptionurl", ""),
                "thumb": info.get("thumburl", ""),
                "width": info.get("width", 0),
            }
        )
    return results


def fetch_image(url: str, dst: Path) -> bool:
    """下载并压缩为 JPEG；宽高不足或下载失败返回 False。"""
    try:
        data = http_get(url)
    except Exception as exc:  # noqa: BLE001 - 单张失败不影响整体
        print(f"    下载失败: {exc}")
        return False
    tmp = dst.with_suffix(".download")
    tmp.write_bytes(data)
    try:
        with Image.open(tmp) as im:
            im = im.convert("RGB")
            if im.width < MIN_WIDTH:
                return False
            if im.width > TARGET_WIDTH:
                ratio = TARGET_WIDTH / im.width
                im = im.resize((TARGET_WIDTH, int(im.height * ratio)), Image.LANCZOS)
            im.save(dst, "JPEG", quality=JPEG_QUALITY, optimize=True, progressive=True)
        return True
    finally:
        tmp.unlink(missing_ok=True)


def strip_html(text: str) -> str:
    import re
    text = re.sub(r"<[^>]+>", " ", text or "")
    return re.sub(r"\s+", " ", text).strip()


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    credits: list[dict] = []
    for prefix, query, count in THEMES:
        print(f"[主题] {prefix}: {query}")
        hits = [h for h in search_ccby(query) if h["title"] not in EXCLUDE_TITLES]
        print(f"  命中 CC-BY 图片 {len(hits)} 张")
        used = 0
        for i, hit in enumerate(hits):
            if used >= count or not hit["thumb"]:
                continue
            time.sleep(1)  # 下载间隔，避免触发限流
            dst = OUT_DIR / f"{prefix}-{used + 1}.jpg"
            if fetch_image(hit["thumb"], dst):
                used += 1
                record = {
                    "file": dst.name,
                    "title": strip_html(hit["title"]),
                    "author": strip_html(hit["artist"]) or "unknown",
                    "license": hit["license"],
                    "source": hit["description_url"],
                }
                credits.append(record)
                print(f"    采用 -> {record['file']} ({dst.stat().st_size // 1024} KB) by {record['author']} [{record['license']}]")
        if used == 0:
            print("  [警告] 该主题未获得可用 CC-BY 图片")
    # 输出署名清单（CC-BY 要求）
    credits_path = OUT_DIR / "CREDITS.json"
    credits_path.write_text(json.dumps(credits, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n完成，共采用 {len(credits)} 张，署名清单 -> {credits_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
