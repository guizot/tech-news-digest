import os
import hashlib
from datetime import datetime, timezone, timedelta

import feedparser
import requests
from dateutil import parser as dateparser
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

# --- Config ---
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID", "")

DIGEST_TITLE = os.getenv("DIGEST_TITLE", "📰 Tech News Digest (Last 24h)")
MAX_ARTICLES = int(os.getenv("MAX_ARTICLES", "25"))

# RSS sources (you can add/remove)
RSS_FEEDS = [
    "https://www.theverge.com/rss/index.xml",
    "https://techcrunch.com/feed/",
    "https://www.wired.com/feed/rss",
    "https://arstechnica.com/feed/",
    "https://www.engadget.com/rss.xml",
    "https://www.technologyreview.com/feed/",
]

# --- Helpers ---
def now_utc() -> datetime:
    return datetime.now(timezone.utc)

def normalize_url(url: str) -> str:
    return (url or "").split("?")[0].strip()

def stable_id(title: str, url: str) -> str:
    raw = (title.strip().lower() + "|" + normalize_url(url)).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:16]

def parse_entry_datetime(entry) -> datetime | None:
    for key in ("published", "updated", "created"):
        if key in entry and entry[key]:
            try:
                dt = dateparser.parse(entry[key])
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt.astimezone(timezone.utc)
            except Exception:
                pass
    return None

def fetch_last_24h_articles():
    cutoff = now_utc() - timedelta(hours=24)
    items = {}

    for feed_url in RSS_FEEDS:
        parsed = feedparser.parse(feed_url)
        source_name = (parsed.feed.get("title") or "Unknown").strip()

        for e in parsed.entries:
            title = (e.get("title") or "").strip()
            link = (e.get("link") or "").strip()
            if not title or not link:
                continue

            dt = parse_entry_datetime(e)
            if dt is None or dt < cutoff:
                continue

            uid = stable_id(title, link)
            if uid not in items or dt > items[uid]["published_at"]:
                items[uid] = {
                    "title": title,
                    "url": normalize_url(link),
                    "published_at": dt,
                    "source": source_name,
                }

    ordered = sorted(items.values(), key=lambda x: x["published_at"], reverse=True)
    return ordered[:MAX_ARTICLES]

def today_label() -> str:
    return datetime.now(timezone.utc).strftime("%b %d, %Y")

def build_summarizer_prompt(articles):
    lines = []
    for i, a in enumerate(articles, start=1):
        ts = a["published_at"].strftime("%Y-%m-%d %H:%M UTC")
        lines.append(
            f"{i}. [{a['source']}] {a['title']} ({ts})\n"
            f"   {a['url']}"
        )
    joined = "\n".join(lines)

    title = f"📰 Tech News Digest (Last 24h) — {today_label()}"

    return f"""
You are a professional tech news editor writing for a Telegram channel.

Rules:
- Output using TELEGRAM HTML formatting.
- Write EXACTLY 5 news items.
- For EACH news item:
  - Start with an emoji
  - Use <b>bold</b> for the headline title
  - On the next line, include ONE plain URL (clickable)
  - Then write ONE paragraph of 4–6 sentences
- Do NOT use Markdown.
- Do NOT invent URLs.
- Do NOT include URLs inside paragraphs.
- Merge duplicate stories.
- Tone: professional, informative.

Required format:

<b>{title}</b>

🚀 <b>Headline title</b>
https://example.com/article

Paragraph summary text with 4–6 sentences.

(Repeat until 5 items)

—
🤖 Auto-generated AI summary  
📡 Sources: TechCrunch, The Verge, Wired, Ars Technica  
⏰ Updated daily at 08:00 (Jakarta time)

Articles:
{joined}
""".strip()


def summarize_digest(articles):
    client = OpenAI(
        api_key=OPENAI_API_KEY,
        base_url="https://openrouter.ai/api/v1"
    )
    prompt = build_summarizer_prompt(articles)

    resp = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": "You write crisp tech digests for busy readers."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.3,
        max_tokens=900,
    )
    return (resp.choices[0].message.content or "").strip()

def escape_md(text: str) -> str:
    escape_chars = r"_*[]()~`>#+-=|{}.!\\"
    return "".join(f"\\{c}" if c in escape_chars else c for c in text)

def telegram_send_markdown(text: str):
    safe_text = escape_md(text)

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHANNEL_ID,
        "text": safe_text,
        "parse_mode": "MarkdownV2",
        "disable_web_page_preview": True,
    }
    r = requests.post(url, json=payload, timeout=30)
    if not r.ok:
        raise RuntimeError(f"Telegram send failed: {r.status_code} {r.text}")

def telegram_send_html(text: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHANNEL_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    r = requests.post(url, json=payload, timeout=30)
    if not r.ok:
        raise RuntimeError(f"Telegram send failed: {r.status_code} {r.text}")

def main():
    missing = []
    if not OPENAI_API_KEY:
        missing.append("OPENAI_API_KEY")
    if not TELEGRAM_BOT_TOKEN:
        missing.append("TELEGRAM_BOT_TOKEN")
    if not TELEGRAM_CHANNEL_ID:
        missing.append("TELEGRAM_CHANNEL_ID")

    # typo guard (in case someone mis-reads)
    # (we keep actual required name TELEGRAM_CHANNEL_ID)
    if missing:
        raise SystemExit(f"Missing env vars: {', '.join(missing)}")

    articles = fetch_last_24h_articles()
    if not articles:
        telegram_send_html(f"**{DIGEST_TITLE}**\n\nNo notable tech items found in the last 24 hours.")
        return

    digest = summarize_digest(articles)
    telegram_send_html(digest)

if __name__ == "__main__":
    main()
