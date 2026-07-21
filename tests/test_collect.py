import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import collect


class FakeEntry(dict):
    pass


class FakeFeed:
    bozo = False

    def __init__(self, entries):
        self.entries = entries


class FakeResponse:
    text = json.dumps(
        {
            "daily_digest": ["1行目", "2行目", "3行目"],
            "articles": [
                {
                    "title": "変更された題名",
                    "summary": "要約です。重要点です。",
                    "why_important": "業界研究に役立ちます。",
                    "category": "業界",
                    "url": "https://example.com/a",
                    "source": "変更された出典",
                }
            ],
        },
        ensure_ascii=False,
    )


class FakeModels:
    def generate_content(self, **kwargs):
        self.kwargs = kwargs
        return FakeResponse()


class FakeClient:
    def __init__(self):
        self.models = FakeModels()


class CollectTests(unittest.TestCase):
    def test_zero_articles_writes_all_json_files_without_api_key(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch.dict(os.environ, {}, clear=True):
                result = collect.summarize_articles([])
            paths = collect.write_outputs(
                result,
                data_dir=Path(temp),
                generated_at=datetime(2026, 7, 20, 21, tzinfo=timezone.utc),
            )
            self.assertTrue(all(path.exists() for path in paths.values()))
            latest = json.loads(paths["latest"].read_text(encoding="utf-8"))
            self.assertEqual(latest["date"], "2026-07-21")
            self.assertEqual(latest["articles"], [])
            self.assertEqual(len(latest["daily_digest"]), 3)

    @patch("collect.feedparser.parse")
    def test_collection_filters_old_and_duplicate_urls(self, parse):
        recent = FakeEntry(
            title="<b>新着</b>",
            summary="<p>概要</p>",
            link="https://example.com/a",
            published_parsed=(2026, 7, 21, 10, 0, 0, 0, 0, 0),
        )
        duplicate = FakeEntry(recent)
        old = FakeEntry(
            title="古い記事",
            summary="概要",
            link="https://example.com/old",
            published_parsed=(2026, 7, 19, 10, 0, 0, 0, 0, 0),
        )
        parse.return_value = FakeFeed([recent, duplicate, old])
        articles = collect.collect_recent_articles(
            [{"name": "テスト", "url": "https://example.com/rss"}],
            now=datetime(2026, 7, 21, 12, tzinfo=timezone.utc),
        )
        self.assertEqual(len(articles), 1)
        self.assertEqual(articles[0]["title"], "新着")

    def test_model_cannot_change_title_or_source(self):
        originals = [
            {
                "title": "RSSの原題",
                "description": "概要",
                "url": "https://example.com/a",
                "source": "RSS出典",
                "published_at": "2026-07-21T10:00:00+00:00",
            }
        ]
        result = collect.summarize_articles(originals, client=FakeClient())
        self.assertEqual(result["articles"][0]["title"], "RSSの原題")
        self.assertEqual(result["articles"][0]["source"], "RSS出典")


if __name__ == "__main__":
    unittest.main()
