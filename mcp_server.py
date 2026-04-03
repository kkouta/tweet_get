from pathlib import Path
from dotenv import load_dotenv
import os
import tweepy
import anthropic
from mcp.server.fastmcp import FastMCP

load_dotenv(Path(__file__).parent / ".env")

mcp = FastMCP("my-tools")


# ハードコードされたユーザー情報 (username -> {id, aliases})
KNOWN_USERS_INFO = {
    "kkouta929":     {"id": "1057566678479847424", "aliases": ["自分", "kkouta", "こうた"]},
    "aya172957":     {"id": "1501063285403426817", "aliases": ["堤", "つつみ", "堤くん"]},
    "kai_brokering": {"id": "1755326513124433922", "aliases": ["kai", "かい", "カイ"]},
}
KNOWN_USERS = {k: v["id"] for k, v in KNOWN_USERS_INFO.items()}

def _resolve_user(username: str) -> tuple[str, str]:
    """音声認識ミスを考慮し、LLM → 文字列距離の順でユーザー名を解決する。"""
    import difflib

    candidates = "\n".join(KNOWN_USERS.keys())
    ai_client = anthropic.Anthropic()
    message = ai_client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=32,
        messages=[{
            "role": "user",
            "content": (
                f"以下はTwitterのユーザー名候補リストです。\n{candidates}\n\n"
                f"音声認識された入力: 「{username}」\n\n"
                f"上のリストの中から最も近いユーザー名を1つだけ答えてください。"
                f"必ずリスト内の文字列をそのままコピーして答えてください。候補にない場合のみ「none」と答えてください。"
            ),
        }],
    )
    matched = message.content[0].text.strip()

    # LLMがリスト内の値を返した場合はそのまま使う
    if matched in KNOWN_USERS:
        return matched, KNOWN_USERS[matched]

    # フォールバック: 文字列距離ベースのマッチング
    fallback = difflib.get_close_matches(username.lower(), KNOWN_USERS.keys(), n=1, cutoff=0.3)
    if fallback:
        return fallback[0], KNOWN_USERS[fallback[0]]

    return username, None

def _twitter_client() -> tweepy.Client:
    return tweepy.Client(
        bearer_token=os.environ["BEARER_TOKEN"],
        consumer_key=os.environ["CK"],
        consumer_secret=os.environ["CS"],
        access_token=os.environ["AT"],
        access_token_secret=os.environ["AS"],
    )


@mcp.tool()
def search_tweets_by_query(query: str) -> str:
    """
    自然言語クエリからユーザーと検索内容を自動判別し、関連ツイートの本文とURLを返す。
    例: 「堤くんのダンスに関するツイート」「kaiさんのハッカソンについて」
    ユーザーへの確認は一切不要。ツイートが見つからない場合もその旨だけ返す。
    """
    candidates = "\n".join(
        f"- {name} (aliases: {', '.join(info['aliases'])})"
        for name, info in KNOWN_USERS_INFO.items()
    )
    ai_client = anthropic.Anthropic()

    # ユーザー名と検索内容を抽出
    extract = ai_client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=64,
        messages=[{
            "role": "user",
            "content": (
                f"登録ユーザー一覧（aliasesは呼び方の候補）:\n{candidates}\n\n"
                f"クエリ: 「{query}」\n\n"
                "クエリに登場する人物に最も近い登録ユーザー名と検索内容を抽出してください。\n"
                "必ず以下の形式のみで答えてください:\n"
                "username: <ユーザー名>\ncontent: <検索内容>"
            ),
        }],
    )
    lines = extract.content[0].text.strip().splitlines()
    username = lines[0].replace("username:", "").strip()
    content = lines[1].replace("content:", "").strip() if len(lines) > 1 else query

    matched_name, user_id = _resolve_user(username)
    tw_client = _twitter_client()
    if user_id is None:
        user = tw_client.get_user(username=matched_name)
        if not user.data:
            return "該当するユーザーが見つかりませんでした。"
        user_id = user.data.id

    response = tw_client.get_users_tweets(user_id, max_results=30)
    if not response.data:
        return "ツイートが見つかりませんでした。"

    tweets = response.data
    tweets_text = "\n".join(f"{i+1}. {t.text}" for i, t in enumerate(tweets))

    # 関連ツイートの番号を選択（内容が曖昧な場合は全件）
    message = ai_client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=64,
        messages=[{
            "role": "user",
            "content": (
                f"ツイート一覧:\n{tweets_text}\n\n"
                f"検索内容: 「{content}」\n\n"
                "関連するツイートの番号をカンマ区切りで答えてください。"
                "検索内容が曖昧または特定のトピックを指定していない場合は全件の番号を返してください。"
                "なければ「なし」。例: 1,3,5"
            ),
        }],
    )
    answer = message.content[0].text.strip()
    if answer == "なし":
        return "該当するツイートが見つかりませんでした。"

    results = []
    for num in answer.split(","):
        try:
            index = int(num.strip()) - 1
            if 0 <= index < len(tweets):
                t = tweets[index]
                url = f"https://x.com/{matched_name}/status/{t.id}"
                results.append(f"{t.text}\n{url}")
        except ValueError:
            continue
    return "\n\n".join(results) if results else "該当するツイートが見つかりませんでした。"

if __name__ == "__main__":
    mcp.run(transport="stdio")
