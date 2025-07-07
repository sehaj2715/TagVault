# BackupThing Telegram Bot Plan

## 1. Technology Stack
*   **Language:** Python
*   **Telegram Bot Framework:** `python-telegram-bot`
*   **Database:** SQLite (via Python's built-in `sqlite3` module) for metadata and user subscriptions.
*   **Configuration:** `.env` file for sensitive data like API tokens.

## 2. Project Structure
```
/
├── .env.example        # Example environment variables
├── .gitignore          # To exclude unnecessary files from Git
├── bot.py              # Main application logic and bot handlers
├── config.py           # To load and manage configuration
├── database.py         # Handles all database interactions
├── plan.md             # The detailed plan you are reading now
└── requirements.txt    # Python dependencies
```

## 3. Core Features
*   **Telegram-Only Operation:** The bot will function entirely within Telegram, with no external websites or storage.
*   **File Upload & Tagging:** Users can upload any file (document, photo, video, etc.) and attach custom tags via the caption. Only the `file_id` and metadata (tags, filename, extension, uploader, timestamp) will be stored in the database.
*   **Instant File Retrieval:** Files will be resent instantly using their stored `file_id`, leveraging Telegram's efficient content delivery network.
*   **Advanced Search & Filtering:** Users can query files by:
    *   Custom tags (single or multiple)
    *   File extensions (e.g., `.pdf`, `.jpg`)
    *   Partial or full filenames
    *   Any combination of the above.
*   **User Management & Subscriptions:**
    *   **Free Tier:** Limited uploads and tags.
    *   **Monthly Plan:** Higher limits, advanced search features.
    *   **Premium Plan:** Highest limits, all features, shared tagged vaults for teams/power users, priority support.
*   **Telegram Payments Integration:** All subscription management and payments will be handled directly through Telegram's Bot API and Payments API, using inline menus.
*   **Inline Menus & Commands:** All bot interactions, including file uploads, search, subscription management, and help, will be managed via Telegram commands and inline keyboard menus.

## 4. Management Commands (Expanded)
*   `/start`: Welcome message and main menu.
*   `/help`: Detailed help and feature overview.
*   `/upload`: Instructions for uploading files with tags.
*   `/search [query]`: Initiate a search based on tags, filename, or extension.
*   `/my_files`: List recently uploaded files by the current user.
*   `/tags`: List all unique tags associated with the user's files.
*   `/delete [query]`: Delete file entries based on a query (filename, tag, etc.).
*   `/subscribe`: Access subscription plans and payment options.
*   `/my_subscription`: View current subscription status and limits.
*   `/shared_vaults`: (Premium only) Manage shared tagged vaults.

## 5. Monetization Strategy
*   **Telegram Payments API:** The primary method for handling subscriptions.
*   **Pricing Tiers:**
    *   **Free:** Basic functionality, limited storage/tags.
    *   **Monthly:** Increased storage/tags, advanced search.
    *   **Premium:** Unlimited storage/tags, shared vaults, priority support.
*   **Inline Payment Flow:** Users will select a plan via inline keyboard, and the bot will initiate the Telegram Payment process.

## 6. Setup and Running
1.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
2.  **Configure environment:**
    *   Rename `.env.example` to `.env`.
    *   Edit `.env` to add your `TELEGRAM_TOKEN`, `ADMIN_ID`, and Telegram Payments Provider Token.
3.  **Run the bot:**
    ```bash
    python bot.py
    ```