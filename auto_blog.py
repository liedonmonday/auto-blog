"""
自動ブログ投稿スクリプト
Gemini API で記事生成 → Blogger に自動投稿
"""

import os
import random
import datetime
import requests
import google.generativeai as genai
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
    "【AIで稼ぐ研究所】AIを使って副業で稼ぐ方法・初心者向け完全ガイド",
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

# =============================
# Gemini で記事生成
# =============================
def generate_article(theme: str) -> dict:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel("gemini-2.0-flash")

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

    response = model.generate_content(prompt)
    article_html = response.text.strip()

    # アフィリエイトリンクを末尾に追加
    affiliate_section = generate_affiliate_section()
    full_content = article_html + affiliate_section

    return {
        "title": theme,
        "content": full_content,
    }


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


# =============================
# メイン処理
# =============================
def main():
    today = datetime.date.today()
    # 日付ベースでテーマをローテーション
    theme_index = today.toordinal() % len(ARTICLE_THEMES)
    theme = ARTICLE_THEMES[theme_index]

    print(f"📝 記事生成中: {theme}")
    article = generate_article(theme)

    print(f"🚀 Bloggerに投稿中...")
    post_to_blogger(article["title"], article["content"])


if __name__ == "__main__":
    main()
