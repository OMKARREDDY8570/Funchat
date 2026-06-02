# 🎲 FunChatBot

Anonymous random chat Telegram bot — like Omegle, but on Telegram.

## Features

- 🎲 **Random Chat** — instant anonymous matching
- 🔍 **Interest Matching** — match by shared topics (Gaming, Anime, Cricket, etc.)
- 👥 **Friend System** — send/accept friend requests anonymously with friend codes
- 🏆 **Leaderboard** — global XP-based rankings
- 🎁 **Daily Rewards** — streak system with coin rewards
- 💰 **Coin Economy** — earn and spend virtual coins
- ⭐ **XP & Levels** — gamified progression system
- 📊 **Reputation** — rate your chat partners
- 🤖 **AI Chat Fallback** — chat with AI when no users are available (optional)
- 🚨 **Safety** — report, block, rate limiting, spam detection, admin panel
- 📢 **Admin Panel** — ban/unban, broadcast, live stats

---

## Project Structure

```
funchatbot/
├── main.py              # Entry point
├── config.py            # Environment config
├── requirements.txt
├── render.yaml          # Render deployment
├── .env.example
├── database/
│   └── db.py           # SQLite async database
├── handlers/
│   ├── start.py        # /start, referrals
│   ├── chat.py         # Core chat: match, relay, skip, end, AI
│   ├── menu.py         # Menu, stats, leaderboard, help
│   ├── profile.py      # User profile view
│   ├── friends.py      # Friend requests and codes
│   ├── rewards.py      # Daily streak rewards
│   ├── settings.py     # User preferences
│   ├── report.py       # Report and block
│   └── admin.py        # Admin commands
└── utils/
    ├── matching.py     # In-memory matching engine
    ├── scheduler.py    # Background tasks
    ├── keyboards.py    # All Telegram keyboard builders
    └── helpers.py      # Formatters, decorators, utilities
```

---

## Local Development Setup

### 1. Prerequisites

- Python 3.11+
- A Telegram Bot Token from [@BotFather](https://t.me/BotFather)

### 2. Clone and install

```bash
git clone <your-repo-url>
cd funchatbot
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Configure environment

```bash
cp .env.example .env
```

Edit `.env`:
```
BOT_TOKEN=your_token_from_botfather
ADMIN_IDS=your_telegram_user_id
DATABASE_PATH=./data/funchatbot.db
```

### 4. Run in polling mode (local)

```bash
mkdir -p data
python main.py
```

Leave `WEBHOOK_URL` empty and the bot runs in polling mode automatically.

---

## Render Free Tier Deployment

### Step 1 — Push to GitHub

```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/yourusername/funchatbot.git
git push -u origin main
```

### Step 2 — Create Render service

1. Go to [render.com](https://render.com) and sign in
2. Click **New → Web Service**
3. Connect your GitHub repo
4. Render will auto-detect `render.yaml`

### Step 3 — Set environment variables

In Render dashboard → your service → **Environment**:

| Variable | Value |
|----------|-------|
| `BOT_TOKEN` | Your bot token from BotFather |
| `ADMIN_IDS` | Your Telegram user ID (e.g. `123456789`) |
| `WEBHOOK_URL` | Your Render URL (e.g. `https://funchatbot.onrender.com`) |
| `DATABASE_PATH` | `/data/funchatbot.db` |
| `AI_API_KEY` | *(optional)* Anthropic API key |

> **Important:** Set `WEBHOOK_URL` to your exact Render service URL **without** trailing slash.

### Step 4 — Deploy

Click **Deploy**. Render will:
1. Install requirements
2. Start the bot in webhook mode
3. Expose `/health` endpoint for uptime monitoring

### Step 5 — Register webhook with Telegram

The bot sets its webhook automatically on startup. You can verify at:
```
https://api.telegram.org/bot<YOUR_TOKEN>/getWebhookInfo
```

---

## Admin Commands

Only users listed in `ADMIN_IDS` can use these:

| Command | Description |
|---------|-------------|
| `/admin` | Open admin panel |
| `/ban <user_id> [reason]` | Ban a user |
| `/unban <user_id>` | Unban a user |
| `/broadcast <message>` | Send message to all users |

---

## Database Schema

SQLite tables:

| Table | Purpose |
|-------|---------|
| `users` | User accounts, ban status, referrals |
| `interests` | User interests for matching |
| `chat_sessions` | Chat history with duration/messages |
| `friend_requests` | Pending/accepted/rejected requests |
| `friendships` | Confirmed friendships with codes |
| `reports` | User reports with status |
| `blocks` | User block list |
| `xp` | XP and level tracking |
| `coins` | Coin balances |
| `coin_transactions` | Full coin transaction history |
| `streaks` | Daily streak tracking |
| `ratings` | Post-chat ratings |
| `daily_stats` | Aggregated daily statistics |
| `rate_limits` | Message rate limiting |

---

## Render Free Tier Notes

- Free tier **spins down** after 15 minutes of inactivity
- Use a free uptime monitor like [UptimeRobot](https://uptimerobot.com) to ping `/health` every 5 minutes to keep it alive
- SQLite data persists on the `/data` disk (1GB included)
- Singapore region is recommended for India-focused users (lowest latency)

---

## Adding AI Chat

Set `AI_API_KEY` to an Anthropic API key. The bot uses `claude-haiku-4-5-20251001` for fast, cheap responses. The feature is automatically enabled when the key is present and gracefully disabled when absent.

---

## License

MIT
