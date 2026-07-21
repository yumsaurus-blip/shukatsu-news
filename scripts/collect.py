"""RSS収集、就活生向けの選別・要約、配信用JSONの保存を行う。"""

from __future__ import annotations

import argparse
import calendar
import html
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from typing import Any

import feedparser
from google import genai
from google.genai import types

from feeds import FEEDS


MODEL = os.getenv("SHUKATSU_NEWS_MODEL", "gemini-3.1-flash-lite")
CATEGORIES = ["経済", "業界", "採用・キャリア", "時事"]
MAX_ARTICLES = 10
WINDOW_HOURS = 24
JST = timezone(timedelta(hours=9))
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_DIR = PROJECT_ROOT / "docs" / "data"


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def strip_html(value: str) -> str:
    """RSS概要に含まれるHTMLをプレーンテキストに変換する。"""
    parser = _TextExtractor()
    try:
        parser.feed(value or "")
        text = " ".join(parser.parts)
    except Exception:
        text = value or ""
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def _entry_datetime(entry: Any) -> datetime | None:
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if not parsed:
        return None
    try:
        return datetime.fromtimestamp(calendar.timegm(parsed), tz=timezone.utc)
    except (OverflowError, TypeError, ValueError):
        return None


def collect_recent_articles(
    feeds: list[dict[str, str]] | None = None,
    *,
    now: datetime | None = None,
) -> list[dict[str, str]]:
    """全RSSから直近24時間の記事を集め、URL単位で重複を除く。"""
    now_utc = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    threshold = now_utc - timedelta(hours=WINDOW_HOURS)
    results: list[dict[str, str]] = []
    seen_urls: set[str] = set()

    for feed in feeds or FEEDS:
        parsed = feedparser.parse(feed["url"])
        if getattr(parsed, "bozo", False):
            print(f"警告: RSSの一部を正常に読めませんでした: {feed['name']}", file=sys.stderr)

        for entry in getattr(parsed, "entries", []):
            url = str(entry.get("link", "")).strip()
            published_at = _entry_datetime(entry)
            if not url or url in seen_urls or not published_at:
                continue
            if not threshold <= published_at <= now_utc + timedelta(minutes=10):
                continue

            title = strip_html(str(entry.get("title", "")))
            if not title:
                continue
            summary = strip_html(str(entry.get("summary") or entry.get("description") or ""))
            seen_urls.add(url)
            results.append(
                {
                    "title": title,
                    "description": summary[:1500],
                    "url": url,
                    "source": feed["name"],
                    "published_at": published_at.isoformat(),
                }
            )

    return sorted(results, key=lambda item: item["published_at"], reverse=True)


NEWS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "daily_digest": {
            "type": "array",
            "items": {"type": "string"},
            "minItems": 3,
            "maxItems": 3,
        },
        "articles": {
            "type": "array",
            "maxItems": MAX_ARTICLES,
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "summary": {"type": "string"},
                    "why_important": {"type": "string"},
                    "category": {"type": "string", "enum": CATEGORIES},
                    "url": {"type": "string"},
                    "source": {"type": "string"},
                },
                "required": [
                    "title",
                    "summary",
                    "why_important",
                    "category",
                    "url",
                    "source",
                ],
                "additionalProperties": False,
            },
        },
    },
    "required": ["daily_digest", "articles"],
    "additionalProperties": False,
}


def empty_digest() -> dict[str, Any]:
    return {
        "daily_digest": [
            "直近24時間の対象RSSに新着記事はありませんでした。",
            "配信元の更新後、次回の自動収集で反映されます。",
            "過去日のニュースは日付ナビから確認できます。",
        ],
        "articles": [],
    }


def summarize_articles(
    articles: list[dict[str, str]],
    *,
    client: Any | None = None,
) -> dict[str, Any]:
    """Gemini APIで重要記事を選別し、指定スキーマで日本語要約する。"""
    if not articles:
        return empty_digest()
    if not os.getenv("GEMINI_API_KEY") and client is None:
        raise RuntimeError("環境変数 GEMINI_API_KEY が設定されていません。")

    api = client or genai.Client()
    candidates = [
        {
            "title": item["title"],
            "description": item["description"],
            "url": item["url"],
            "source": item["source"],
            "published_at": item["published_at"],
        }
        for item in articles
    ]
    prompt = (
        "以下はRSSから取得した直近24時間の記事候補です。候補の中だけから、"
        "就活生が経済・業界研究・採用動向・面接の時事対策で押さえる価値が高い記事を"
        f"最大{MAX_ARTICLES}件選んでください。記事本文を見たふりはせず、与えたタイトルと概要だけを"
        "根拠に、summaryは2〜3文、why_importantは1文で日本語作成してください。"
        "URL、原題、出典は候補の値を一字も変更せず返してください。daily_digestは今日の重要点を"
        "重複しない3行でまとめてください。\n\n"
        + json.dumps(candidates, ensure_ascii=False)
    )

    last_error: Exception | None = None
    for attempt in range(3):
        try:
            response = api.models.generate_content(
                model=MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=(
                        "あなたは就活生向けニュース編集者です。"
                        "事実を補わず、簡潔で自然な日本語を使います。"
                    ),
                    response_mime_type="application/json",
                    response_json_schema=NEWS_SCHEMA,
                    temperature=0.2,
                ),
            )
            parsed = getattr(response, "parsed", None)
            if not isinstance(parsed, dict):
                parsed = json.loads(response.text)
            return _normalize_summary(parsed, articles)
        except Exception as exc:  # API由来の例外型をSDKの版に依存させない
            last_error = exc
            if attempt < 2:
                time.sleep(2**attempt)
    raise RuntimeError(f"Gemini APIによる要約に3回失敗しました: {last_error}") from last_error


def _normalize_summary(result: dict[str, Any], originals: list[dict[str, str]]) -> dict[str, Any]:
    """モデル出力のURLを候補と照合し、RSS由来の原題・出典を復元する。"""
    by_url = {item["url"]: item for item in originals}
    normalized: list[dict[str, str]] = []
    used: set[str] = set()
    for item in result.get("articles", [])[:MAX_ARTICLES]:
        url = str(item.get("url", ""))
        original = by_url.get(url)
        if not original or url in used:
            continue
        category = item.get("category")
        if category not in CATEGORIES:
            category = "時事"
        normalized.append(
            {
                "title": original["title"],
                "summary": str(item.get("summary", "")).strip(),
                "why_important": str(item.get("why_important", "")).strip(),
                "category": category,
                "url": url,
                "source": original["source"],
                "published_at": original["published_at"],
            }
        )
        used.add(url)

    digest = [str(line).strip() for line in result.get("daily_digest", []) if str(line).strip()]
    while len(digest) < 3:
        digest.append("詳しくは各記事の就活生ポイントを確認してください。")
    return {"daily_digest": digest[:3], "articles": normalized}


def write_outputs(
    summary: dict[str, Any],
    *,
    data_dir: Path = DEFAULT_DATA_DIR,
    generated_at: datetime | None = None,
) -> dict[str, Path]:
    """日別、最新、日付一覧の3種のJSONをUTF-8で保存する。"""
    timestamp = (generated_at or datetime.now(timezone.utc)).astimezone(JST)
    date_text = timestamp.date().isoformat()
    payload = {
        "date": date_text,
        "generated_at": timestamp.isoformat(),
        "daily_digest": summary["daily_digest"],
        "articles": summary["articles"],
    }
    data_dir.mkdir(parents=True, exist_ok=True)
    dated_path = data_dir / f"news-{date_text}.json"
    latest_path = data_dir / "latest.json"
    index_path = data_dir / "index.json"

    encoded = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    dated_path.write_text(encoded, encoding="utf-8")
    latest_path.write_text(encoded, encoding="utf-8")

    dates: set[str] = {date_text}
    if index_path.exists():
        try:
            current = json.loads(index_path.read_text(encoding="utf-8"))
            values = current.get("dates", current) if isinstance(current, dict) else current
            dates.update(value for value in values if isinstance(value, str))
        except (json.JSONDecodeError, OSError, TypeError):
            print("警告: index.jsonを再作成します。", file=sys.stderr)
    index_payload = {"dates": sorted(dates, reverse=True)}
    index_path.write_text(
        json.dumps(index_payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return {"dated": dated_path, "latest": latest_path, "index": index_path}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="就活ニュースを収集・要約して配信用JSONを生成します。")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=DEFAULT_DATA_DIR,
        help="JSON出力先（既定: docs/data）",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    now = datetime.now(timezone.utc)
    articles = collect_recent_articles(now=now)
    print(f"収集した記事: {len(articles)}件")
    summary = summarize_articles(articles)
    paths = write_outputs(summary, data_dir=args.data_dir, generated_at=now)
    print(f"配信用JSONを生成しました: {paths['dated']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
