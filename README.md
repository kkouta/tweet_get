# VoiceOS MCP Server

音声入力に対応したTwitter（X）ツイート検索MCPサーバー。

## セットアップ

### 1. 依存パッケージのインストール

```bash
pip3 install mcp tweepy anthropic python-dotenv --break-system-packages
```

### 2. .env の作成

```
BEARER_TOKEN = "your_bearer_token"
CK = "your_api_key"
CS = "your_api_key_secret"
AT = "your_access_token"
AS = "your_access_token_secret"
ANTHROPIC_API_KEY=your_anthropic_api_key
```

> **注意**: `AS` の行末に改行を入れてから `ANTHROPIC_API_KEY` を書いてください。連結されると認証エラーになります。

### 3. Claude Code への登録

```bash
claude mcp add my-tools python3 /path/to/mcp_server.py
```

登録後、Claude Code を再起動するとツールが有効になります。

---

## ツール

### `search_tweets_by_query`

自然言語クエリからユーザーと検索内容を自動判別し、関連ツイートの本文とURLを返します。

**引数**

| 引数 | 型 | 説明 |
|---|---|---|
| `query` | string | 自然言語で入力（例: 「堤くんのAIに関するツイート」） |

**使用例**

```
堤くんのツイートを教えて
kaiさんのハッカソンについて
自分の最新投稿
```

**返答形式**

```
ツイートの本文
https://x.com/username/status/xxxxxxxx

ツイートの本文
https://x.com/username/status/xxxxxxxx
```

---

## 登録ユーザー

| 表示名 | username | 呼び方 |
|---|---|---|
| 自分 | kkouta929 | 自分 / kkouta / こうた |
| 堤くん | aya172957 | 堤 / つつみ / 堤くん |
| kai | kai_brokering | kai / かい / カイ |

ユーザーを追加する場合は `mcp_server.py` の `KNOWN_USERS_INFO` に追記してください。

```python
KNOWN_USERS_INFO = {
    "new_username": {"id": "ユーザーID", "aliases": ["呼び方1", "呼び方2"]},
}
```

---

## ユーザー名解決の仕組み

音声認識ミスを考慮して、2段階でユーザー名を解決します。

1. **LLMマッチング** — エイリアス情報をもとにClaudeが最も近いユーザーを判定
2. **文字列距離フォールバック** — LLMが候補外の値を返した場合、difflib で再マッチング
