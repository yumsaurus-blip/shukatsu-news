"""ニュース収集元の定義。RSSを追加するときはこの配列に追記する。"""

FEEDS = [
    {
        "name": "NHKニュース（経済）",
        "url": "https://www.nhk.or.jp/rss/news/cat5.xml",
    },
    {
        "name": "NHKニュース（主要）",
        "url": "https://www.nhk.or.jp/rss/news/cat0.xml",
    },
    {
        "name": "ITmedia ビジネスオンライン",
        "url": "https://rss.itmedia.co.jp/rss/2.0/business.xml",
    },
    {
        "name": "東洋経済オンライン",
        "url": "https://toyokeizai.net/list/feed/rss",
    },
    {
        "name": "NHKニュース（政治）",
        "url": "https://www.nhk.or.jp/rss/news/cat4.xml",
    },
    {
        "name": "NHKニュース（国際）",
        "url": "https://www.nhk.or.jp/rss/news/cat6.xml",
    },
    {
        "name": "ITmedia NEWS",
        "url": "https://rss.itmedia.co.jp/rss/2.0/news_bursts.xml",
    },
    {
        "name": "プレジデントオンライン",
        "url": "https://president.jp/list/rss",
    },
    {
        "name": "日経クロステック",
        "url": "https://xtech.nikkei.com/rss/index.rdf",
    },
    {
        "name": "Yahoo!ニュース（ビジネス）",
        "url": "https://news.yahoo.co.jp/rss/topics/business.xml",
    },
]
