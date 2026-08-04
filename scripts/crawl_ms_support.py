"""Crawl public Microsoft Support (zh-CN) pages into Markdown.

Compliance:
  - Honors robots.txt (urllib.robotparser)
  - Prefer sitemap discovery (allowed) over search scraping (/search Disallow)
  - Rate-limited + identifiable User-Agent
  - Stores source_url metadata; demo/research only

Usage:
  cd backend
  uv run python ../scripts/crawl_ms_support.py --discover --per-product 3
  uv run python ../scripts/crawl_ms_support.py --seeds-file ../data/raw/microsoft/seeds.json
  uv run python ../scripts/crawl_ms_support.py --ingest
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
import urllib.parse
import urllib.robotparser
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup, NavigableString, Tag

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "data" / "knowledge" / "microsoft"
RAW_DIR = ROOT / "data" / "raw" / "microsoft" / "html"
MANIFEST = ROOT / "data" / "raw" / "microsoft" / "crawl_manifest.json"
SEEDS_FILE = ROOT / "data" / "raw" / "microsoft" / "seeds.json"

ROBOTS_URL = "https://support.microsoft.com/robots.txt"
SITEMAP_COLLECTION = "https://support.microsoft.com/sitemap/collection.xml"
USER_AGENT = (
    "DeepSupportOS-ResearchBot/0.1 "
    "(+https://github.com/daetz-coder/DeepSupport-OS; educational demo crawler)"
)

# Known-good curated seeds (verified 200)
CURATED: list[dict[str, str]] = [
    {
        "product": "Outlook",
        "category": "SendReceive",
        "url": "https://support.microsoft.com/zh-CN/Outlook/i-can-t-send-or-receive-messages-in-outlook",
    },
    {
        "product": "Outlook",
        "category": "Sync",
        "url": "https://support.microsoft.com/zh-CN/Outlook/outlook-email-stuck",
    },
]

PRODUCT_RULES: list[tuple[str, list[str]]] = [
    ("Outlook", ["outlook"]),
    ("Teams", ["teams", "microsoft-teams"]),
    ("OneDrive", ["onedrive"]),
    ("Excel", ["excel"]),
    ("Word", ["word"]),
    ("PowerPoint", ["powerpoint"]),
    ("Microsoft365", ["account-billing", "microsoft-365", "office"]),
]

TROUBLE_KEYS = [
    "无法",
    "不能",
    "修复",
    "同步",
    "登录",
    "激活",
    "闪退",
    "卡死",
    "停滞",
    "密码",
    "许可证",
    "麦克风",
    "摄像头",
    "无声音",
    "fix",
    "troubleshoot",
    "can-t",
    "cant",
    "not-working",
    "stuck",
    "sign-in",
    "password",
    "sync",
    "activation",
    "crash",
    "freeze",
    "microphone",
    "camera",
    "error",
]


def slugify(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r"[^\w\u4e00-\u9fff\-]+", "-", text, flags=re.UNICODE)
    text = re.sub(r"-+", "-", text).strip("-")
    return text[:80] or "doc"


def load_robots() -> urllib.robotparser.RobotFileParser:
    rp = urllib.robotparser.RobotFileParser()
    rp.set_url(ROBOTS_URL)
    try:
        rp.read()
    except Exception as exc:  # noqa: BLE001
        print(f"warning: robots.txt read failed: {exc}")
    return rp


def allowed(rp: urllib.robotparser.RobotFileParser, url: str) -> bool:
    try:
        return rp.can_fetch(USER_AGENT, url)
    except Exception:  # noqa: BLE001
        return False


def html_to_markdown(root: Tag) -> str:
    lines: list[str] = []

    def walk(node: Tag | NavigableString, depth: int = 0) -> None:
        if isinstance(node, NavigableString):
            text = str(node).strip()
            if text:
                lines.append(text)
            return
        if not isinstance(node, Tag):
            return
        name = (node.name or "").lower()
        if name in {"script", "style", "noscript", "nav", "footer", "header", "aside"}:
            return
        if name in {"h1", "h2", "h3", "h4"}:
            level = int(name[1])
            text = node.get_text(" ", strip=True)
            if text:
                lines.append("\n" + "#" * level + " " + text + "\n")
            return
        if name == "li":
            text = node.get_text(" ", strip=True)
            if text:
                lines.append(f"- {text}")
            return
        if name == "p":
            text = node.get_text(" ", strip=True)
            if text:
                lines.append("\n" + text + "\n")
            return
        if name == "a":
            text = node.get_text(" ", strip=True)
            href = node.get("href") or ""
            if text and href:
                lines.append(f"[{text}]({href})")
            elif text:
                lines.append(text)
            return
        if name == "br":
            lines.append("\n")
            return
        for child in node.children:
            walk(child, depth + 1)

    walk(root)
    md = "\n".join(lines)
    return re.sub(r"\n{3,}", "\n\n", md).strip()


def extract_article(html: str) -> tuple[str, str]:
    soup = BeautifulSoup(html, "lxml")
    title = ""
    h1 = soup.find("h1")
    if h1:
        title = h1.get_text(" ", strip=True)
    elif soup.title:
        title = soup.title.get_text(" ", strip=True)

    main = soup.find("main") or soup.find("article")
    if main is None:
        candidates = []
        for el in soup.find_all(["div", "section", "article"]):
            text = el.get_text(" ", strip=True)
            if len(text) > 500:
                candidates.append((len(text), el))
        candidates.sort(key=lambda x: x[0], reverse=True)
        main = candidates[0][1] if candidates else soup.body
    body_md = html_to_markdown(main) if main else ""
    return title, body_md


def write_markdown(
    *,
    product: str,
    category: str,
    title: str,
    url: str,
    body: str,
    fetched_at: str,
) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    doc_id = hashlib.sha1(url.encode("utf-8")).hexdigest()[:12]
    slug = slugify(title) or doc_id
    path = OUT_DIR / f"{product.lower()}-{slug}-{doc_id}.md"
    safe_title = title.replace('"', "")
    content = "\n".join(
        [
            "---",
            f'title: "{safe_title}"',
            f"product: {product}",
            f"category: {category}",
            f"source_url: {url}",
            "language: zh-CN",
            f"fetched_at: {fetched_at}",
            f"document_id: ms-{doc_id}",
            "content_type: Troubleshooting",
            "---",
            "",
            f"# {title}",
            "",
            f"> 来源: [{url}]({url})",
            "",
            body,
            "",
            "---",
            "",
            "本页由 DeepSupport OS 研究爬虫采集自 Microsoft 公开支持文档，仅用于本地演示检索；请遵守 Microsoft 服务条款与版权要求。",
            "",
        ]
    )
    path.write_text(content, encoding="utf-8")
    return path


def classify_product(url: str) -> str | None:
    path = urllib.parse.unquote(urlparse_path(url)).lower()
    for product, keys in PRODUCT_RULES:
        if any(k in path for k in keys):
            # avoid mis-bucket generic office into Word via 'password'
            if product == "Word" and "password" in path and "word" not in path:
                continue
            return product
    return None


def urlparse_path(url: str) -> str:
    return urllib.parse.urlparse(url).path


def is_trouble(url: str) -> bool:
    decoded = urllib.parse.unquote(url).lower()
    return any(k.lower() in decoded for k in TROUBLE_KEYS)


def discover_seeds(client: httpx.Client, per_product: int) -> list[dict[str, str]]:
    r = client.get(SITEMAP_COLLECTION, follow_redirects=True, timeout=45.0)
    r.raise_for_status()
    locs = re.findall(r"<loc>([^<]+)</loc>", r.content.decode("utf-8-sig"))
    zh_sitemaps = [u for u in locs if re.search(r"/zh-cn/sitemap/", u, re.I)]
    buckets: dict[str, list[str]] = {p: [] for p, _ in PRODUCT_RULES}
    filled = lambda: all(len(buckets[p]) >= per_product for p, _ in PRODUCT_RULES)

    for sm in zh_sitemaps:
        if filled():
            break
        try:
            resp = client.get(sm, follow_redirects=True, timeout=30.0)
            urls = re.findall(r"<loc>([^<]+)</loc>", resp.content.decode("utf-8-sig"))
        except Exception as exc:  # noqa: BLE001
            print(f"sitemap fail {sm}: {exc}")
            continue
        for u in urls:
            product = classify_product(u)
            if not product:
                continue
            if len(buckets[product]) >= per_product:
                continue
            if is_trouble(u) or len(buckets[product]) < max(1, per_product // 2):
                if u not in buckets[product]:
                    buckets[product].append(u)
        time.sleep(0.25)

    seeds: list[dict[str, str]] = []
    seen = set()
    for s in CURATED:
        if s["url"] not in seen:
            seeds.append(s)
            seen.add(s["url"])
    for product, urls in buckets.items():
        for u in urls:
            if u in seen:
                continue
            seeds.append(
                {
                    "product": product,
                    "category": "Troubleshooting" if is_trouble(u) else "Guide",
                    "url": u,
                }
            )
            seen.add(u)
    return seeds


def try_ingest_raglab(md_path: Path, raglab_url: str) -> dict[str, Any]:
    try:
        with md_path.open("rb") as f:
            files = {"file": (md_path.name, f, "text/markdown")}
            data = {"kb": "huawei", "title": md_path.stem, "doc_type": "support"}
            headers = {"X-Role": "editor"}
            r = httpx.post(
                f"{raglab_url.rstrip('/')}/api/ingest",
                files=files,
                data=data,
                headers=headers,
                timeout=60.0,
            )
        return {"ok": r.status_code < 300, "status": r.status_code, "body": r.text[:500]}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)}


def crawl(
    seeds: list[dict[str, str]],
    *,
    delay: float,
    ingest: bool,
    raglab_url: str,
) -> dict[str, Any]:
    rp = load_robots()
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, Any]] = []
    headers = {
        "User-Agent": USER_AGENT,
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
    }

    with httpx.Client(headers=headers) as client:
        for i, seed in enumerate(seeds, start=1):
            url = seed["url"]
            item: dict[str, Any] = {
                "url": url,
                "product": seed["product"],
                "category": seed.get("category", "Guide"),
            }
            if not allowed(rp, url):
                item["status"] = "disallowed_robots"
                results.append(item)
                print(f"[{i}/{len(seeds)}] SKIP robots {url}")
                continue
            try:
                resp = None
                for attempt in range(1, 4):
                    resp = client.get(url, follow_redirects=True, timeout=45.0)
                    if resp.status_code != 403:
                        break
                    wait = delay * attempt * 2
                    print(f"[{i}/{len(seeds)}] HTTP 403 retry {attempt}/3 sleep {wait:.1f}s")
                    time.sleep(wait)
                assert resp is not None
                item["http_status"] = resp.status_code
                item["final_url"] = str(resp.url)
                if resp.status_code >= 400:
                    item["status"] = "http_error"
                    results.append(item)
                    print(f"[{i}/{len(seeds)}] HTTP {resp.status_code}")
                    time.sleep(delay)
                    continue
                raw_name = hashlib.sha1(url.encode()).hexdigest()[:12] + ".html"
                (RAW_DIR / raw_name).write_bytes(resp.content)
                title, body = extract_article(resp.text)
                if len(body) < 200:
                    item["status"] = "too_short"
                    item["title"] = title
                    results.append(item)
                    print(f"[{i}/{len(seeds)}] SHORT {title or url}")
                    time.sleep(delay)
                    continue
                fetched_at = datetime.now(timezone.utc).isoformat()
                path = write_markdown(
                    product=seed["product"],
                    category=seed.get("category", "Guide"),
                    title=title or seed["product"],
                    url=str(resp.url),
                    body=body,
                    fetched_at=fetched_at,
                )
                item.update(
                    {
                        "status": "ok",
                        "title": title,
                        "path": str(path.relative_to(ROOT)).replace("\\", "/"),
                        "chars": len(body),
                    }
                )
                if ingest:
                    item["ingest"] = try_ingest_raglab(path, raglab_url)
                results.append(item)
                print(f"[{i}/{len(seeds)}] OK {title} ({len(body)} chars)")
            except Exception as exc:  # noqa: BLE001
                item["status"] = "error"
                item["error"] = str(exc)
                results.append(item)
                print(f"[{i}/{len(seeds)}] ERR {exc}")
            time.sleep(delay)

    ok = sum(1 for r in results if r.get("status") == "ok")
    # Sanitize results for valid JSON (strip control chars in titles/errors)
    clean_results = json.loads(
        json.dumps(results, ensure_ascii=False, default=str).encode("utf-8", "replace").decode("utf-8")
    )
    summary = {
        "crawled_at": datetime.now(timezone.utc).isoformat(),
        "user_agent": USER_AGENT,
        "seed_count": len(seeds),
        "ok": ok,
        "failed": len(results) - ok,
        "results": clean_results,
        "note": "Public Microsoft Support pages via sitemap/seeds; demo use only.",
    }
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--discover", action="store_true", help="Discover seeds from zh-CN sitemaps")
    parser.add_argument("--per-product", type=int, default=3)
    parser.add_argument("--seeds-file", type=Path, default=None)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--delay", type=float, default=1.2)
    parser.add_argument("--ingest", action="store_true")
    parser.add_argument("--raglab-url", default="http://127.0.0.1:8001")
    args = parser.parse_args()

    headers = {"User-Agent": USER_AGENT, "Accept-Language": "zh-CN,zh;q=0.9"}
    if args.seeds_file and args.seeds_file.exists():
        seeds = json.loads(args.seeds_file.read_text(encoding="utf-8"))
    elif args.discover:
        print("discovering seeds from sitemap...")
        with httpx.Client(headers=headers, timeout=120.0) as client:
            seeds = discover_seeds(client, args.per_product)
        SEEDS_FILE.parent.mkdir(parents=True, exist_ok=True)
        SEEDS_FILE.write_text(json.dumps(seeds, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"wrote {SEEDS_FILE} ({len(seeds)} seeds)")
    else:
        seeds = list(CURATED)
        if SEEDS_FILE.exists():
            seeds = json.loads(SEEDS_FILE.read_text(encoding="utf-8"))

    if args.limit:
        seeds = seeds[: args.limit]

    summary = crawl(
        seeds,
        delay=args.delay,
        ingest=args.ingest,
        raglab_url=args.raglab_url,
    )
    print(json.dumps({"ok": summary["ok"], "failed": summary["failed"], "manifest": str(MANIFEST)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
