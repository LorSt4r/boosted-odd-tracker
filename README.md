# Boosted Odds Monitor

An asynchronous Python automation tool that monitors boosted sports odds, records newly observed entries, and sends real-time notifications.

This project detects and tracks advertised boosted odds. It **does not** estimate true event probabilities, expected value, or betting profitability, and it should not be described as a predictive or machine-learning model.

## Features

- Monitors a dynamic single-page application with Playwright.
- Uses `asyncio` and `aiohttp` for non-blocking browser and notification work.
- Sends new-entry alerts through the Telegram Bot API.
- Stores history locally and can append records to Google Sheets.
- Includes retry/backoff behavior, content hashing, and optional health-check pings.

## Stack

- Python 3
- Playwright
- `asyncio` / `aiohttp`
- Telegram Bot API
- Google Sheets API (`gspread`)

## Setup

```bash
git clone https://github.com/LorSt4r/boosted-odd-tracker.git
cd boosted-odd-tracker
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
cp .env.example .env
```

Fill in the required values in `.env`, then run:

```bash
python superquote_checker.py
```

Google Sheets and health-check integration are optional. Keep service-account JSON and all API tokens outside version control.

## Configuration

| Variable | Required | Purpose |
|---|---:|---|
| `TELEGRAM_BOT_TOKEN` | Yes | Telegram bot authentication token |
| `TELEGRAM_CHAT_IDS` | Yes | Comma-separated target chat IDs |
| `SUPERQUOTE_HISTORY_FILE` | No | Local JSON history path |
| `HEALTHCHECK_URL` | No | External heartbeat endpoint |
| `GOOGLE_SHEETS_CREDENTIALS_FILE` | No | Path to a Google service-account JSON file |
| `GOOGLE_SHEETS_SPREADSHEET_ID` | No | Target spreadsheet ID |
| `GOOGLE_SHEETS_WORKSHEET_NAME` | No | Target worksheet name |

## Scope and responsible use

The project is an educational automation experiment. Website structure may change without notice, and use of automated browsing must comply with applicable law and the target site's terms. No prediction, financial advice, or guarantee of availability is provided.

## License

MIT — see [LICENSE](LICENSE).
