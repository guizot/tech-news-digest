# Tech News Digest → Telegram (GitHub Actions)

This project fetches tech news from RSS feeds from the last 24 hours, summarizes into 3–5 headline stories with bullet points (1–3 sentences per bullet), then posts to a Telegram channel.

## 1) Setup Telegram
1. Create a bot via @BotFather and copy the token.
2. Add the bot as an admin in your Telegram channel (permission to post).
3. Set `TELEGRAM_CHANNEL_ID`:
   - Public: @your_channel_username
   - Private: -100xxxxxxxxxx

## 2) Local run
Copy `.env.example` to `.env` and fill values.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

## 3) GitHub Actions schedule (08:00 Asia/Jakarta)
GitHub cron uses UTC. 08:00 Jakarta (UTC+7) = 01:00 UTC.

Workflow: `.github/workflows/tech_digest.yml`

Add these repo secrets:
- OPENAI_API_KEY
- TELEGRAM_BOT_TOKEN
- TELEGRAM_CHANNEL_ID
