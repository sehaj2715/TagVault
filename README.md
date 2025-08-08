## BackupThing

### Project Summary

BackupThing is a Telegram bot that allows users to back up their files with associated tags. The bot provides functionalities to search for files using tags, filenames, or extensions, and to manage file metadata such as names and tags. While the files are stored on Telegram's servers, the metadata is kept in a PostgreSQL database. Additionally, a lightweight Flask web server is included to expose a health check endpoint.

### Tools and Technologies

*   **Backend:** Python
*   **Telegram Bot Framework:** `python-telegram-bot`
*   **Database:** PostgreSQL (interfaced with `psycopg2-binary`)
*   **Web Server:** Flask
*   **Configuration:** `python-dotenv` for managing environment variables

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