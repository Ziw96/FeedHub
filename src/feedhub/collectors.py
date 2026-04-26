from __future__ import annotations

import hashlib
import re
from datetime import timezone, datetime
from email.utils import parsedate_to_datetime
from html import unescape
from html.parser import HTMLParser
from typing import List
from urllib.parse import urljoin
from urllib.request import Request, urlopen
from xml.etree import ElementTree

from .models import Item, Source, utc_now_iso
from .x import load_x_config, x_api_get_json


USER_AGENT = "FeedHub/0.1"
NOISY_TAGS = {
    "button",
    "footer",
    "form",
    "head",
    "header",
    "iframe",
    "nav",
    "noscript",
    "script",
    "style",
    "svg",
    "template",
}
CONTENT_TAGS = {"article", "main", "section"}
BLOCK_TAGS = {"p", "li", "h1", "h2", "h3", "h4", "article", "main", "section", "div"}
NOISY_HINTS = {
    "banner",
    "breadcrumb",
    "cookie",
    "footer",
    "header",
    "menu",
    "nav",
    "newsletter",
    "search",
    "share",
    "sidebar",
    "social",
    "subscribe",
}


def fetch_source_items(source: Source) -> List[Item]:
    if source.type == "rss":
        return _fetch_rss(source)
    if source.type == "html":
        return _fetch_html_snapshot(source)
    if source.type == "x":
        return _fetch_x_posts(source)
    raise ValueError(f"Unsupported source type: {source.type}")


def _fetch_url(url: str) -> str:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=20) as response:
        return response.read().decode("utf-8", errors="replace")


def _fetch_rss(source: Source) -> List[Item]:
    xml_text = _fetch_url(source.url)
    root = ElementTree.fromstring(xml_text)
    items: List[Item] = []
    for node in root.findall(".//item"):
        title = _node_text(node, "title") or source.name
        url = _node_text(node, "link") or source.url
        summary = _clean_text(_node_text(node, "description") or "")
        published_at = _parse_pub_date(_node_text(node, "pubDate"))
        content_hash = _hash_for(title, url, summary)
        items.append(
            Item(
                source_id=source.id,
                source_name=source.name,
                title=title,
                url=url,
                collected_at=utc_now_iso(),
                published_at=published_at,
                summary=summary,
                content_hash=content_hash,
                official=source.official,
                priority=source.priority,
            )
        )
    return items


def _fetch_html_snapshot(source: Source) -> List[Item]:
    page_url = source.url
    html = _fetch_url(page_url)
    if source.latest_link_pattern:
        latest_url = _find_latest_link(html, source.url, source.latest_link_pattern)
        if latest_url:
            page_url = latest_url
            html = _fetch_url(page_url)

    parser = _ReadableHTMLParser()
    parser.feed(html)
    parser.close()

    title = parser.best_title() or source.name
    summary = parser.summary()
    content_hash = _hash_for(title, page_url, summary)
    return [
        Item(
            source_id=source.id,
            source_name=source.name,
            title=title,
            url=page_url,
            collected_at=utc_now_iso(),
            published_at=datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            summary=summary,
            content_hash=content_hash,
            official=source.official,
            priority=source.priority,
        )
    ]


def _fetch_x_posts(source: Source) -> List[Item]:
    handle = source.handle.lstrip("@")
    if not handle:
        raise ValueError(f"X source {source.id} is missing a handle")

    config = load_x_config()
    max_items = source.max_items or config.default_max_items
    if max_items < 1:
        raise ValueError(f"X source {source.id} max_items must be greater than 0")

    user_payload = x_api_get_json(
        f"/2/users/by/username/{handle}",
        {"user.fields": "id,name,username"},
        config,
    )
    user = user_payload.get("data") or {}
    user_id = user.get("id", "")
    username = user.get("username", handle)
    if not user_id:
        raise RuntimeError(f"X account lookup returned no user for @{handle}")

    posts_payload = x_api_get_json(
        f"/2/users/{user_id}/tweets",
        {
            "exclude": ["replies", "retweets"],
            "max_results": min(max_items, 100),
            "tweet.fields": "created_at,in_reply_to_user_id,note_tweet,referenced_tweets,text",
        },
        config,
    )

    items: List[Item] = []
    for post in posts_payload.get("data", []):
        if not _is_supported_x_post(post):
            continue
        text = _clean_text(_x_post_text(post))
        if not text:
            continue
        url = f"https://x.com/{username}/status/{post.get('id', '')}"
        summary = _truncate_text(text, 500)
        title = _truncate_text(text, 80)
        items.append(
            Item(
                source_id=source.id,
                source_name=source.name,
                title=title or source.name,
                url=url,
                collected_at=utc_now_iso(),
                published_at=_parse_iso_datetime(post.get("created_at", "")),
                summary=summary,
                content_hash=_hash_for(title or source.name, url, summary),
                official=source.official,
                priority=source.priority,
            )
        )
    return items


def _node_text(node: ElementTree.Element, name: str) -> str:
    child = node.find(name)
    return child.text.strip() if child is not None and child.text else ""


def _parse_pub_date(raw: str) -> str:
    if not raw:
        return ""
    try:
        return parsedate_to_datetime(raw).astimezone(timezone.utc).replace(microsecond=0).isoformat()
    except (TypeError, ValueError, IndexError):
        return ""


def _clean_text(value: str) -> str:
    value = unescape(value or "")
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def _truncate_text(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    shortened = value[:limit].rsplit(" ", 1)[0].strip()
    return shortened or value[:limit].strip()


def _hash_for(title: str, url: str, summary: str) -> str:
    payload = f"{title}|{url}|{summary}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _x_post_text(post: dict) -> str:
    note_tweet = post.get("note_tweet") or {}
    return str(note_tweet.get("text") or post.get("text") or "")


def _is_supported_x_post(post: dict) -> bool:
    if post.get("in_reply_to_user_id"):
        return False
    references = post.get("referenced_tweets") or []
    blocked_types = {"retweeted", "reposted"}
    return not any(reference.get("type") in blocked_types for reference in references)


def _parse_iso_datetime(raw: str) -> str:
    if not raw:
        return ""
    normalized = raw.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized).astimezone(timezone.utc).replace(microsecond=0).isoformat()
    except ValueError:
        return ""


class _ReadableHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._ignored_stack: List[str] = []
        self._content_depth = 0
        self._capture_title = False
        self._tag_stack: List[str] = []
        self._block_buffer: List[str] = []
        self._blocks: List[tuple[str, int]] = []
        self._document_title = ""
        self._meta_title = ""

    def handle_starttag(self, tag: str, attrs: List[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        self._tag_stack.append(tag)
        attrs_map = {name.lower(): (value or "") for name, value in attrs}

        if tag == "meta":
            self._capture_meta(attrs_map)
            return

        if tag == "title":
            self._capture_title = True
            return

        if self._should_ignore(tag, attrs_map):
            self._ignored_stack.append(tag)
            return

        if tag in CONTENT_TAGS:
            self._content_depth += 1

        if tag in BLOCK_TAGS:
            self._flush_block()

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag == "title":
            self._capture_title = False

        if self._ignored_stack and tag == self._ignored_stack[-1]:
            self._ignored_stack.pop()
        elif tag in CONTENT_TAGS and self._content_depth:
            self._content_depth -= 1

        if tag in BLOCK_TAGS:
            self._flush_block()

        if self._tag_stack:
            self._tag_stack.pop()

    def handle_data(self, data: str) -> None:
        text = _clean_text(data)
        if not text:
            return
        if self._capture_title:
            self._document_title = self._append_text(self._document_title, text)
            return
        if self._ignored_stack:
            return
        weight = 2 if self._content_depth else 1
        self._block_buffer.append(text)
        if len(self._block_buffer) > 120:
            self._flush_block(weight=weight)

    def best_title(self) -> str:
        for candidate in (self._meta_title, self._document_title):
            cleaned = _clean_text(candidate)
            if cleaned:
                return cleaned
        if self._blocks:
            return self._blocks[0][0][:120]
        return ""

    def summary(self, limit: int = 500) -> str:
        self._flush_block()
        if not self._blocks:
            return ""

        ranked = sorted(
            self._blocks,
            key=lambda item: (item[1], len(item[0])),
            reverse=True,
        )
        seen = set()
        segments: List[str] = []
        for text, _weight in ranked:
            normalized = _normalize_for_summary(text)
            if not normalized or normalized in seen:
                continue
            if len(normalized) < 40 and segments:
                continue
            if _looks_like_css_or_script(normalized):
                continue
            seen.add(normalized)
            segments.append(normalized)
            joined = " ".join(segments)
            if len(joined) >= limit:
                return joined[:limit].rsplit(" ", 1)[0]
        return " ".join(segments)[:limit]

    def _capture_meta(self, attrs_map: dict[str, str]) -> None:
        key = (attrs_map.get("property") or attrs_map.get("name") or "").lower()
        content = _clean_text(attrs_map.get("content", ""))
        if key in {"og:title", "twitter:title"} and content:
            self._meta_title = content

    def _should_ignore(self, tag: str, attrs_map: dict[str, str]) -> bool:
        if tag in NOISY_TAGS:
            return True
        hint_text = " ".join(
            [attrs_map.get("id", ""), attrs_map.get("class", ""), attrs_map.get("role", "")]
        ).lower()
        return any(hint in hint_text for hint in NOISY_HINTS)

    def _flush_block(self, weight: int | None = None) -> None:
        if not self._block_buffer:
            return
        text = _normalize_for_summary(" ".join(self._block_buffer))
        self._block_buffer = []
        if not text or len(text) < 20:
            return
        if _looks_like_css_or_script(text):
            return
        current_weight = weight if weight is not None else (2 if self._content_depth else 1)
        self._blocks.append((text, current_weight))

    @staticmethod
    def _append_text(existing: str, text: str) -> str:
        if not existing:
            return text
        return f"{existing} {text}"


def _normalize_for_summary(value: str) -> str:
    value = _clean_text(value)
    value = re.sub(r"\s*[|\\/]+\s*", " | ", value)
    return value.strip(" -|")


def _looks_like_css_or_script(value: str) -> bool:
    lowered = value.lower()
    signals = (
        "@keyframes",
        "function(",
        "var ",
        "stroke-dashoffset",
        "transform:",
        "document.",
        "window.",
    )
    return any(signal in lowered for signal in signals)


def _find_latest_link(html: str, base_url: str, pattern: str) -> str:
    hrefs = re.findall(r"""<a[^>]+href=["']([^"'#]+)["']""", html, flags=re.IGNORECASE)
    for href in hrefs:
        full_url = urljoin(base_url, unescape(href))
        if pattern in full_url:
            return full_url
    return ""
