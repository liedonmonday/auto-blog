"""
自動ブログ投稿スクリプト
Gemini API で記事生成 → Blogger に自動投稿
"""

import os
import datetime
import requests
from requests import HTTPError
from google import genai
from google.genai.errors import ClientError
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

# =============================
# 設定（GitHub Secretsから取得）
# =============================
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
BLOGGER_BLOG_ID = os.environ["BLOGGER_BLOG_ID"]
BLOGGER_REFRESH_TOKEN = os.environ["BLOGGER_REFRESH_TOKEN"]
BLOGGER_CLIENT_ID = os.environ["BLOGGER_CLIENT_ID"]
BLOGGER_CLIENT_SECRET = os.environ["BLOGGER_CLIENT_SECRET"]

# Buffer連携（未設定でもブログ投稿は継続）
BUFFER_ACCESS_TOKEN = os.environ.get("BUFFER_ACCESS_TOKEN")
BUFFER_PROFILE_ID = os.environ.get("BUFFER_PROFILE_ID")
BUFFER_SETUP_CHECK = os.environ.get("BUFFER_SETUP_CHECK", "false").lower() == "true"
BUFFER_API_FLAVOR = os.environ.get("BUFFER_API_FLAVOR", "auto").lower()  # auto | rest | graphql
BUFFER_GRAPHQL_URL = os.environ.get("BUFFER_GRAPHQL_URL", "https://api.buffer.com/graphql")
BUFFER_ORGANIZATION_ID = os.environ.get("BUFFER_ORGANIZATION_ID")

# アフィリエイトリンク（もしもアフィリエイト等に差し替え）
AFFILIATE_LINKS = [
    {
        "name": "おすすめ副業ツール",
        "url": "https://your-affiliate-link-1.com",
        "description": "月収10万円を目指す人に人気のツール"
    },
    {
        "name": "AI副業講座",
        "url": "https://your-affiliate-link-2.com",
        "description": "初心者でも始められるAI副業の完全ガイド"
    },
]

# 記事テーマリスト（自動でローテーション）
ARTICLE_THEMES = [
    "​【AIで稼ぐ研究所】AIを使って副業で稼ぐ方法・初心者向け完全ガイド",
    "【AIで稼ぐ研究所】ChatGPTで月5万円稼ぐ具体的な方法",
    "【AIで稼ぐ研究所】自動化ツールを使って不労所得を作る方法",
    "【AIで稼ぐ研究所】ブログアフィリエイトをAIで効率化する手順",
    "【AIで稼ぐ研究所】Gemini APIを使った副業アイデア5選",
    "【AIで稼ぐ研究所】AIツールで稼ぐおすすめ副業ランキング2025年版",
    "【AIで稼ぐ研究所】在宅でできるAI副業を始める前に知っておくべきこと",
    "【AIで稼ぐ研究所】AIライティングツールで記事作成を自動化する方法",
    "【AIで稼ぐ研究所】アフィリエイト初心者がAIで月3万円達成した手順",
    "【AIで稼ぐ研究所】副業でAIを活用するためのおすすめツール比較",
    "【AIで稼ぐ研究所】Claude APIで稼ぐ方法・使い方と副業活用術",
    "【AIで稼ぐ研究所】AI画像生成で副業収入を得る具体的な方法",
    "【AIで稼ぐ研究所】GitHub Actionsで副業を完全自動化する手順",
    "【AIで稼ぐ研究所】AIツールだけで月10万円を目指すロードマップ",
]

# Buffer無料プラン想定: 月10投稿
X_POSTING_DAYS = [1, 4, 7, 10, 13, 16, 19, 22, 25, 28]

# =============================
# Gemini で記事生成
# =============================
def generate_article(theme: str) -> dict:
    client = genai.Client(api_key=GEMINI_API_KEY)

    prompt = f"""
あなたはSEOに強いブログライターです。
「AIで稼ぐ研究所」というブログのために、以下のテーマで日本語のブログ記事をHTML形式で書いてください。

テーマ：{theme}

条件：
- 文字数：1500〜2000文字
- 見出し（h2, h3）を使って読みやすく構成する
- 読者は副業初心者
- 自然な文体で親しみやすく
- ブログ名「AIで稼ぐ研究所」らしい研究・実験的なトーンを意識する
- 最後に「まとめ」セクションを入れる
- HTMLのbodyタグの中身だけ出力する（htmlタグ不要）

記事本文のみ出力してください。
"""

    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=prompt,
    )
    article_html = response.text.strip()

    # アフィリエイトリンクを末尾に追加
    affiliate_section = generate_affiliate_section()
    full_content = article_html + affiliate_section

    return {
        "title": theme,
        "content": full_content,
    }


def is_gemini_quota_error(exc: Exception) -> bool:
    """Geminiのクォータ超過エラーかどうかを判定"""
    message = str(exc).lower()
    has_quota_keyword = "resource_exhausted" in message or "quota" in message

    # ClientErrorのときはHTTPステータスも確認
    if isinstance(exc, ClientError):
        return exc.code == 429 and has_quota_keyword

    # 例外型が異なる環境差分でも、メッセージで判定して安全にスキップする
    return has_quota_keyword and "429" in message


def generate_affiliate_section() -> str:
    """アフィリエイトリンクのHTMLセクションを生成"""
    html = "\n<h2>おすすめツール・サービス</h2>\n<ul>\n"
    for link in AFFILIATE_LINKS:
        html += f'  <li><a href="{link["url"]}" target="_blank" rel="nofollow">{link["name"]}</a>：{link["description"]}</li>\n'
    html += "</ul>\n"
    return html


# =============================
# Blogger へ投稿
# =============================
def get_blogger_service():
    """Blogger APIクライアントを取得"""
    token_url = "https://oauth2.googleapis.com/token"
    data = {
        "client_id": BLOGGER_CLIENT_ID,
        "client_secret": BLOGGER_CLIENT_SECRET,
        "refresh_token": BLOGGER_REFRESH_TOKEN,
        "grant_type": "refresh_token",
    }
    response = requests.post(token_url, data=data)
    access_token = response.json()["access_token"]

    creds = Credentials(token=access_token)
    service = build("blogger", "v3", credentials=creds)
    return service


def post_to_blogger(title: str, content: str):
    """Bloggerに記事を投稿"""
    service = get_blogger_service()

    post_body = {
        "title": title,
        "content": content,
    }

    post = service.posts().insert(
        blogId=BLOGGER_BLOG_ID,
        body=post_body,
        isDraft=False,
    ).execute()

    print(f"✅ 投稿完了: {post['url']}")
    return post


def should_post_to_x(date: datetime.date) -> bool:
    """Buffer無料プランの上限（月10投稿）に収めるための判定"""
    return date.day in X_POSTING_DAYS


def build_x_post_text(title: str, post_url: str) -> str:
    """X向け投稿文を作成"""
    hashtags = "#AI副業 #ブログ更新"
    text = f"【新着記事】{title}\n{post_url}\n{hashtags}"
    return text[:280]


def post_to_buffer_x(text: str):
    """Buffer経由でXに投稿予約（next=trueで最短キュー）"""
    if not BUFFER_ACCESS_TOKEN or not BUFFER_PROFILE_ID:
        print("⚠️ Buffer設定が未完了のため、X投稿をスキップしました。")
        return None

    if BUFFER_API_FLAVOR == "graphql":
        print("⚠️ BUFFER_API_FLAVOR=graphql の場合、自動投稿は未対応です。X投稿をスキップします。")
        return None

    url = "https://api.bufferapp.com/1/updates/create.json"
    payload = {
        "access_token": BUFFER_ACCESS_TOKEN,
        "profile_ids[]": BUFFER_PROFILE_ID,
        "text": text,
        "shorten": "true",
        "now": "false",
        "top": "true",
    }

    response = requests.post(url, data=payload, timeout=30)
    try:
        response.raise_for_status()
    except HTTPError as exc:
        detail = response.text[:500]
        raise RuntimeError(
            "Buffer APIにアクセスできません。"
            "BufferのPublic APIは現在再構築中のため、"
            "Developer APIのアクセス権が必要な場合があります。"
            f" status={response.status_code}, body={detail}"
        ) from exc

    result = response.json()

    if not result.get("success"):
        raise RuntimeError(f"Buffer投稿に失敗しました: {result}")

    print("✅ Bufferキューへの追加完了（X連携）")
    return result


def get_buffer_profiles():
    """Buffer連携済みプロフィール一覧を取得（設定確認用）"""
    if not BUFFER_ACCESS_TOKEN:
        raise RuntimeError("BUFFER_ACCESS_TOKEN が未設定です。")

    url = "https://api.bufferapp.com/1/profiles.json"
    response = requests.get(
        url,
        params={"access_token": BUFFER_ACCESS_TOKEN},
        timeout=30,
    )
    try:
        response.raise_for_status()
    except HTTPError as exc:
        detail = response.text[:500]
        raise RuntimeError(
            "Bufferプロフィール取得に失敗しました。"
            "BufferのPublic APIは再構築中のため、"
            "現時点ではDeveloper APIアクセスが必要な可能性があります。"
            f" status={response.status_code}, body={detail}"
        ) from exc

    return response.json()


def run_buffer_graphql(query: str) -> dict:
    """Buffer GraphQL APIを呼び出す"""
    if not BUFFER_ACCESS_TOKEN:
        raise RuntimeError("BUFFER_ACCESS_TOKEN が未設定です。")

    response = requests.post(
        BUFFER_GRAPHQL_URL,
        json={"query": query},
        headers={"Authorization": f"Bearer {BUFFER_ACCESS_TOKEN}"},
        timeout=30,
    )
    response.raise_for_status()

    body = response.json()
    if body.get("errors"):
        raise RuntimeError(f"Buffer GraphQLエラー: {body['errors']}")
    return body.get("data", {})


def normalize_graphql_channels(raw_channels):
    """GraphQLレスポンス差分を吸収してchannels配列へ正規化"""
    if isinstance(raw_channels, list):
        return raw_channels

    if isinstance(raw_channels, dict):
        if isinstance(raw_channels.get("nodes"), list):
            return raw_channels["nodes"]
        if isinstance(raw_channels.get("items"), list):
            return raw_channels["items"]

    return []


def get_channels_input_candidates():
    """GraphQL channels(input) の候補を返す"""
    candidates = ["{}"]
    if BUFFER_ORGANIZATION_ID:
        org = BUFFER_ORGANIZATION_ID.replace('"', '\\"')
        candidates.insert(0, f'{{organizationId: "{org}"}}')
    return candidates


def get_buffer_channels_graphql():
    """Buffer GraphQLのchannels情報を取得（Personal API Beta向け）"""
    query_templates = [
        """
        query {
          account {
            id
          }
          channels(input: __CHANNELS_INPUT__) {
            id
            service
          }
        }
        """,
        """
        query {
          account {
            id
          }
          channels(input: __CHANNELS_INPUT__) {
            nodes {
              id
              service
            }
          }
        }
        """,
        """
        query {
          channels(input: __CHANNELS_INPUT__) {
            id
            service
          }
        }
        """,
        """
        query {
          channels(input: __CHANNELS_INPUT__) {
            nodes {
              id
              service
            }
          }
        }
        """,
    ]

    last_error = None
    for channels_input in get_channels_input_candidates():
        for template in query_templates:
            query = template.replace("__CHANNELS_INPUT__", channels_input)
            try:
                data = run_buffer_graphql(query)
                raw_channels = data.get("channels", [])
                channels = normalize_graphql_channels(raw_channels)
                account = data.get("account", {})
                if channels:
                    return account, channels
                last_error = RuntimeError("channelsが空、または想定外の構造です。")
            except Exception as exc:  # noqa: BLE001
                last_error = exc

    raise RuntimeError(
        "GraphQLからchannels取得に失敗しました。"
        f" BUFFER_ORGANIZATION_IDの指定も確認してください。詳細: {last_error}"
    )


def run_buffer_setup_check():
    """Buffer設定確認モード（プロフィール一覧表示）"""
    print("🔍 Buffer設定チェックを開始します...")
    profiles = None

    if BUFFER_API_FLAVOR in ("auto", "graphql"):
        try:
            account, channels = get_buffer_channels_graphql()
            account_id = account.get("id", "unknown") if isinstance(account, dict) else "unknown"
            print(f"✅ GraphQL接続成功: account_id={account_id}")
            print("✅ 連携済みチャンネル一覧:")
            for channel in channels:
                service = channel.get("service", "unknown")
                channel_id = channel.get("id")
                print(f"- service={service}, id={channel_id}")

            if BUFFER_PROFILE_ID:
                matched = any(str(channel.get("id")) == str(BUFFER_PROFILE_ID) for channel in channels)
                if matched:
                    print(f"✅ BUFFER_PROFILE_ID({BUFFER_PROFILE_ID}) は有効です。")
                else:
                    print(f"⚠️ BUFFER_PROFILE_ID({BUFFER_PROFILE_ID}) が一覧内に見つかりません。値を再確認してください。")
            else:
                print("ℹ️ BUFFER_PROFILE_ID は未設定です。上記idをGitHub Secretsへ設定してください。")
            return
        except Exception as exc:  # noqa: BLE001
            if BUFFER_API_FLAVOR == "graphql":
                raise RuntimeError(f"GraphQL設定チェックに失敗しました: {exc}") from exc
            print(f"ℹ️ GraphQLでの設定確認に失敗したためREST APIで再試行します: {exc}")

    profiles = get_buffer_profiles()

    if not profiles:
        print("⚠️ 連携済みプロフィールが見つかりません。Buffer側でXチャンネル連携を確認してください。")
        return

    print("✅ 連携済みプロフィール一覧:")
    for profile in profiles:
        service = profile.get("service", "unknown")
        handle = profile.get("formatted_username") or profile.get("service_username") or "(ユーザー名なし)"
        profile_id = profile.get("id")
        print(f"- service={service}, handle={handle}, id={profile_id}")

    if BUFFER_PROFILE_ID:
        matched = any(str(profile.get("id")) == str(BUFFER_PROFILE_ID) for profile in profiles)
        if matched:
            print(f"✅ BUFFER_PROFILE_ID({BUFFER_PROFILE_ID}) は有効です。")
        else:
            print(f"⚠️ BUFFER_PROFILE_ID({BUFFER_PROFILE_ID}) が一覧内に見つかりません。値を再確認してください。")
    else:
        print("ℹ️ BUFFER_PROFILE_ID は未設定です。上記idをGitHub Secretsへ設定してください。")


# =============================
# メイン処理
# =============================
def main():
    if BUFFER_SETUP_CHECK:
        run_buffer_setup_check()
        return

    today = datetime.date.today()
    theme_index = today.toordinal() % len(ARTICLE_THEMES)
    theme = ARTICLE_THEMES[theme_index]

    print(f"📝 記事生成中: {theme}")
    try:
        article = generate_article(theme)
    except Exception as exc:  # noqa: BLE001
        if is_gemini_quota_error(exc):
            print("⚠️ Gemini APIのクォータ上限に達したため、本日の記事生成をスキップします。")
            print("ℹ️ Google AI Studio の利用量・課金設定をご確認ください。")
            return
        raise

    print(f"🚀 Bloggerに投稿中...")
    post = post_to_blogger(article["title"], article["content"])

    if should_post_to_x(today):
        x_text = build_x_post_text(article["title"], post["url"])
        print("🐦 Buffer経由でX投稿キューに追加中...")
        post_to_buffer_x(x_text)
    else:
        print("ℹ️ 本日はX投稿スキップ日です（月10投稿制限のため）。")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001
        if is_gemini_quota_error(exc):
            print("⚠️ Gemini APIのクォータ上限に達したため、今回の実行はスキップします。")
            print("ℹ️ Google AI Studio の利用量・課金設定をご確認ください。")
        else:
            raise
