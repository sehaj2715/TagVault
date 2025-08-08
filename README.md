## BackupThing

Telegram bot to back up files with tags, search them, and manage metadata. Files remain on Telegram; metadata lives in Postgres. A tiny Flask server exposes a health check.

### Prerequisites

- Python 3.10+
- Postgres (reachable via `DATABASE_URL`)

### Setup

- Install deps: `pip install -r requirements.txt`
- Create a `.env` file with:
  - `TELEGRAM_TOKEN=...`
  - `DATABASE_URL=postgresql://user:pass@host:5432/dbname`
  - `ADMIN_ID=123456789` (your Telegram user ID)
  - `TELEGRAM_PAYMENTS_PROVIDER_TOKEN=...`
- Ensure the Postgres tables exist: `users`, `files`, `tags`, `file_tags`.

### Run

- Start the bot: `python bot.py`
- Health check: `GET http://localhost:5000/ping` → returns `Pong!`

### Use

- Upload: send a file to the bot with a caption like: `My important document #work projectX`
- Search: send any text (matches filename, extension, or tags)
- Commands:
  - `/start` — main menu
  - `/files [page]` — recent files
  - `/tags` — your tags
  - `/delete <query>` — delete by name or `#tag`
  - `/edit <file_query> [name:new] [tags:[add|remove|set] ...]` — rename/retag

