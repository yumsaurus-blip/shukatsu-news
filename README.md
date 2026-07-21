# シューカツタイムズ

就活生が知っておきたい経済・業界・採用・時事ニュースをRSSから毎朝収集し、Gemini APIで最大10件に選別・要約して配信する静的PWAです。APIキーはGitHub Actionsだけが使用し、ブラウザには渡りません。

## 仕組み

1. GitHub Actionsが毎朝6:00（日本時間）に公開RSSの直近24時間分を収集します。
2. `gemini-3.1-flash-lite` が就活生に重要な記事を選び、3行まとめと記事カード用の日本語要約を作ります。
3. `docs/data/` の日別JSON、`latest.json`、`index.json`を更新して自動コミットします。
4. GitHub Pages上のPWAがJSONを読み込みます。記事本文の取得やスクレイピングは行いません。

## ローカルで確認する

Python 3.12を用意し、リポジトリ直下で次を実行します。

```powershell
python -m venv "$env:LOCALAPPDATA\ShukatsuNews\venv"
& "$env:LOCALAPPDATA\ShukatsuNews\venv\Scripts\Activate.ps1"
python -m pip install -r scripts\requirements.txt
$env:GEMINI_API_KEY = [Environment]::GetEnvironmentVariable("GEMINI_API_KEY", "User")
python scripts\collect.py
python -m http.server 8000 --directory docs
```

ブラウザで `http://localhost:8000` を開きます。APIキーを設定しない場合でも、同梱JSONで画面だけ確認できます。APIキーを `.env` やソースコードへ書かないでください。

テストは次のコマンドで実行できます。

```powershell
python -m unittest discover -s tests -v
```

## GitHubへ公開する

1. GitHubで公開リポジトリ `shukatsu-news` を作成して、このフォルダーをpushします。
2. **Settings → Secrets and variables → Actions** でRepository secret `GEMINI_API_KEY` を登録します。
3. **Settings → Pages** のSourceを **Deploy from a branch**、公開元を `main` ブランチの `/docs` にします。
4. **Actions → 毎朝のニュース更新 → Run workflow** を手動実行します。
5. 実行後、`docs/data/latest.json` が更新され、PagesのURLで記事カードが表示されることを確認します。

ActionsがJSONをcommitするため、Workflow permissionsには読み書き権限が必要です。ワークフローでは `contents: write` を宣言済みです。

## PWAとオフライン動作

`manifest.json` とService Workerを同梱しています。静的ファイルはキャッシュ優先、ニュースJSONはネットワーク優先で取得し、通信できないときだけ前回のキャッシュを表示します。PWAのインストール判定にはHTTPSが必要ですが、`localhost` とGitHub Pagesはいずれも条件を満たします。

## モデル設定

既定モデルは無料枠の `gemini-3.1-flash-lite` です。変更する場合は `SHUKATSU_NEWS_MODEL` 環境変数を使用します。

```powershell
$env:SHUKATSU_NEWS_MODEL = "gemini-3.1-flash-lite"
```

## 動作確認済み環境

- Windows 11 Home（10.0.26200）
- Python 3.12.12
- google-genai 1.75.0
- 2026年7月22日：RSS候補187件から10件を要約し、3行まとめと4カテゴリを生成
- 自動テスト3件成功

詳しい結果は [docs/動作確認メモ.md](docs/動作確認メモ.md) を参照してください。

## 既知の制限と注意事項

- AI要約には誤りや不足があり得ます。面接や応募判断に使う際は、必ず出典リンクを確認してください。
- RSSのタイトルと概要だけを要約し、記事本文は読みません。概要が短い記事は要約の情報量も少なくなります。
- Gemini無料枠にはレート制限があり、入力内容がGoogleの製品改善に使われる場合があります。公開RSS以外の機密情報を入力しないでください。
- API失敗時は2回再試行し、合計3回失敗すると処理を終了します。直前の `latest.json` は残ります。
- Googleドライブ配下に仮想環境を作らないでください。

## RSSを追加する

`scripts/feeds.py` の `FEEDS` に名前とRSS URLを追加します。利用規約を確認し、公開RSSだけを登録してください。
