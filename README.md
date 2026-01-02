# News Forecast Scheduler Telegram Bot

## Project Overview
This Telegram bot delivers scheduled news forecasts to subscribers. It integrates with the News Forecast Europe API (`/news-json`) to analyze market trends and news topics across multiple countries.

**Key Features:**
*   **Subscriptions:** Users can subscribe/unsubscribe via Telegram commands.
*   **Scheduling:** Forecasts run automatically at configured UTC times.
*   **Persistence:** Subscriber data and execution history are stored in SQLite.
*   **Multi-Topic Delivery:** Sends detailed analysis for each configured topic.
*   **Reliability:** Prevents duplicate sends on restart and includes API retry logic.

## Requirements
*   Python 3.11+
*   Dependencies: `python-telegram-bot`, `httpx`, `APScheduler`, `python-dotenv`

## Setup

1.  **Clone the repository**:
    ```bash
    git clone <repo-url>
    cd news-forecast-tgbot
    ```

2.  **Create and activate a virtual environment**:
    ```bash
    python -m venv venv
    # Windows
    .\venv\Scripts\activate
    # Linux/Mac
    source venv/bin/activate
    ```

3.  **Install dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

4.  **Configuration**:
    Create a `.env` file in the root directory (copy from snippet below).
    The database will be automatically created at `bot_database.db` on first run.

## Configuration (.env)

Create a file named `.env` and add the following:

```env
BOT_TOKEN=your_telegram_bot_token_here
API_BASE_URL=https://news-forecast-europe-663528033484.us-west1.run.app
SQLITE_PATH=bot_database.db
ADMIN_IDS=12345678,87654321
REQUEST_TIMEOUT_SEC=60
```
*   `ADMIN_IDS`: Comma-separated list of Telegram User IDs who can manage schedules.

## Running the Bot

Run the bot with:
```bash
python main.py
```
*   The bot will initialize the `bot_database.db` SQLite file.
*   If no schedules exist, a default "Morning Briefing" schedule (08:00 UTC) is created.

**Date/Time Note:** All scheduling is in **UTC**.

## Usage

### User Commands
*   `/start` - Welcome message and help.
*   `/subscribe` - Subscribe to daily forecasts.
*   `/unsubscribe` - Stop receiving forecasts.
*   `/status` - Check if you are currently subscribed.

### Admin Commands (Restricted to ADMIN_IDS)
*   `/schedule_list` - View all configured forecast schedules (ID, time, parameters).
*   `/subscribers_count` - View total active subscribers.
*   `/run_now <schedule_id>` - Manually trigger a specific schedule immediately.
    *   By default, this sends the report **only to the admin** requesting it, for testing purposes.
    *   To broadcast to *all subscribers* manually, this requires code modification or a flag iteration (default behavior in code is Admin-only for safety).

## Editing Schedules
By default, the bot runs with **SQLite-backed schedules**.
To edit schedules, you can currently use a standard SQLite browser (like `DB Browser for SQLite`) to modify the `forecast_schedules` table.
*   `time_utc`: Format "HH:MM" (24h).
*   `countries`: CSV (e.g., "fr,de,uk").
*   `topics`: CSV (e.g., "top_headlines,economy").
*   `language`: "en", "fr", "de", etc.

## Troubleshooting
*   **Bot not sending messages?** Check `schedule_runs` table in DB for "success" status. If it says "success", the bot thinks it already ran today.
*   **API Errors?** Check logs (`main.py` outputs to console). Retries are automatic for 5xx errors.
*   **Telegram 429?** The bot handles rate limits by sleeping, but massive broadcasts might take time.
*   **Using `/#/` in URL?** The bot logic automatically strips trailing slashes and appends `/news-json`.

## Project Structure
*   `main.py`: Entry point, sets up Application and Scheduler.
*   `database.py`: SQLite schema and data access layer.
*   `scheduler_service.py`: Job logic, API calls, and message broadcasting.
*   `api_client.py`: Async HTTP client for the Forecast API.
*   `handlers.py`: Telegram command handlers (`/subscribe`, etc.).
*   `formatter.py`: HTML formatting logic for messages.
*   `registries.py`: Country and Language validation data.
*   `config.py`: Environment variable loading.

## Acceptance
This bot meets the following criteria:
*   [x] Subscriptions persist in SQLite.
*   [x] Schedules execution at UTC time.
*   [x] Valid API URL construction and JSON parsing.
*   [x] Multi-topic chunked messaging.
*   [x] Deduplication of runs.
*   [x] Graceful error handling.
