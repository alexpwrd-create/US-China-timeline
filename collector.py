import hashlib
import json
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import feedparser
import requests
import yaml

ROOT = Path(__file__).parent
DATA = ROOT / "data"
CONFIG = yaml.safe_load((ROOT / "sources.yml").read_text(encoding="utf-8"))

DATA.mkdir(exist_ok=True)
PENDING_PATH = DATA / "pending.json"
EVENTS_PATH = DATA / "events.json"

HEADERS = {
    "User-Agent": "USChinaTimelineBot/1.0 (public-interest research; contact: repository maintainer)"
}
TIMEOUT = 25

def read_json(path):
    if not path.exists():
        return []
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, list) else []
    except (json.JSONDecodeError, OSError):
        return []

def write_json(path, value):
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

def canonical_url(url):
    """去掉常见追踪参数，便于按网址去重。"""
    try:
        parsed = urlparse(url.strip())
        tracking = ("utm_", "fbclid", "gclid", "ref")
        query = [
            (key, value)
            for key, value in parse_qsl(parsed.query, keep_blank_values=True)
            if not key.lower().startswith(tracking)
        ]
        return urlunparse((
            parsed.scheme.lower(),
            parsed.netloc.lower().removeprefix("www."),
            parsed.path.rstrip("/"),
            "",
            urlencode(query),
            "",
        ))
    except Exception:
        return url.strip()

def parse_date(value):
    if not value:
        return ""

    if isinstance(value, (tuple, list)):
        try:
            return datetime(*value[:6], tzinfo=timezone.utc).date().isoformat()
        except (TypeError, ValueError):
            return ""

    text = str(value).strip()
    for fmt in ("%Y%m%dT%H%M%SZ", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            pass

    try:
        parsed = parsedate_to_datetime(text)
        return parsed.date().isoformat()
    except (TypeError, ValueError, OverflowError):
        pass

    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        return ""

def keyword_found(text, keyword):
    """英文短词按词边界匹配，减少 US 等短词误命中。"""
    text = text.lower()
    keyword = keyword.lower().strip()
    if not keyword:
        return False

    if keyword.isascii() and re.fullmatch(r"[a-z0-9. -]+", keyword):
        pattern = r"(?<![a-z0-9])" + re.escape(keyword) + r"(?![a-z0-9])"
        return re.search(pattern, text) is not None

    return keyword in text

def classify(text):
    us_words = [
        "united states", "u.s.", "american", "washington",
        "美国", "中美"
    ]
    china_words = [
        "china", "chinese", "beijing", "中国", "中美"
    ]

    # 初版采取较严格筛选：标题或文本须同时涉及美国和中国
    if not any(has_keyword(text, word) for word in us_words):
        return None
    if not any(has_keyword(text, word) for word in china_words):
        return None

    for category, words in CONFIG.get("topic_keywords", {}).items():
        if any(has_keyword(text, word) for word in words):
            return category

    return None

def make_id(url):
    return hashlib.sha1(canonical_url(url).encode("utf-8")).hexdigest()[:14]

def approved_urls(events):
    result = set()
    for event in events:
        url = event.get("source_url", "")
        if not url:
            for source in event.get("sources", []):
                url = source.get("url", "")
                if url:
                    break
        if url:
            result.add(canonical_url(url))
    return result

def feed_candidates():
    candidates = []

    for feed in CONFIG.get("feeds", []):
        try:
            response = requests.get(feed["url"], headers=HEADERS, timeout=TIMEOUT)
            response.raise_for_status()
            parsed = feedparser.parse(response.content)

            if parsed.bozo and not parsed.entries:
                raise ValueError(str(parsed.bozo_exception))

            for entry in parsed.entries:
                title = (entry.get("title") or "").strip()
                url = (entry.get("link") or "").strip()
                if not title or not url:
                    continue

                excerpt = re.sub(
                    r"\s+", " ",
                    re.sub(r"<[^>]+>", " ", entry.get("summary", "") or ""),
                ).strip()

                category = classify(title, excerpt)
                if not category:
                    continue

                published = (
                    entry.get("published_parsed")
                    or entry.get("updated_parsed")
                    or entry.get("published")
                    or entry.get("updated")
                )

                candidates.append({
                    "id": make_id(url),
                    "date": parse_date(published),
                    "title": title,
                    "source_name": feed["name"],
                    "source_type": feed.get("type", "media"),
                    "source_url": url,
                    "category": category,
                    "excerpt": excerpt[:1200],
                })

            print(f"OK RSS: {feed['name']} — {len(parsed.entries)} entries")

        except Exception as exc:
            print(f"RSS ERROR: {feed.get('name', feed.get('url'))}: {exc}")

    return candidates

def domain_is_trusted(domain, trusted_domains):
    domain = (domain or "").lower().removeprefix("www.")
    return any(
        domain == trusted or domain.endswith("." + trusted)
        for trusted in trusted_domains
    )

def gdelt_candidates():
    settings = CONFIG.get("gdelt", {})
    if not settings.get("enabled", False):
        return []

    trusted_domains = settings.get("trusted_domains", [])
    # GDELT 查询用于发现线索；域名白名单负责基础来源筛选。
    query = (
        '"United States" China '
        '(diplomacy OR summit OR tariff OR sanctions OR '
        '"export controls" OR Taiwan OR semiconductor OR AI)'
    )

    try:
        response = requests.get(
            "https://api.gdeltproject.org/api/v2/doc/doc",
            params={
                "query": query,
                "mode": "ArtList",
                "format": "json",
                "sort": "DateDesc",
                "maxrecords": settings.get("max_records", 50),
                "timespan": settings.get("lookback", "24h"),
            },
            headers=HEADERS,
            timeout=TIMEOUT,
        )
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:
        print(f"GDELT ERROR: {exc}")
        return []

    candidates = []
    for article in payload.get("articles", []):
        title = (article.get("title") or "").strip()
        url = (article.get("url") or "").strip()
        domain = article.get("domain", "")

        if not title or not url or not domain_is_trusted(domain, trusted_domains):
            continue

        excerpt = (article.get("seendate") or "").strip()
        category = classify(title, excerpt)
        if not category:
            continue

        candidates.append({
            "id": make_id(url),
            "date": parse_date(article.get("seendate")),
            "title": title,
            "source_name": domain,
            "source_type": "media",
            "source_url": url,
            "category": category,
            "excerpt": "",
        })

    print(f"OK GDELT: {len(candidates)} trusted candidates")
    return candidates

def main():
    existing_pending = read_json(PENDING_PATH)
    approved = read_json(EVENTS_PATH)

    known_urls = approved_urls(approved)
    known_urls.update(
        canonical_url(item.get("source_url", ""))
        for item in existing_pending
        if item.get("source_url")
    )

    collected = feed_candidates() + gdelt_candidates()
    added = []
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")

    for item in collected:
        url_key = canonical_url(item["source_url"])
        if not url_key or url_key in known_urls:
            continue

        known_urls.add(url_key)
        item["status"] = "pending"
        item["collected_at"] = now
        added.append(item)

    if added:
        write_json(PENDING_PATH, existing_pending + added)

    print(f"Added {len(added)} new candidates; pending total: {len(existing_pending) + len(added)}")

if __name__ == "__main__":
    main()
