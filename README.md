# 📈 Superquote Tracker & Value Bet Bot

A fully automated Python tool designed to detect market inefficiencies in sports betting odds (Value Bets) in real-time. This project combines web scraping, API integration, and statistical analysis to track "Superquotes" (boosted odds) on Bet365.

## 🚀 Key Features
* **Real-Time Monitoring:** Scrapes odds 24/7 using **Playwright** to handle dynamic Single Page Applications (SPAs).
* **Instant Notifications:** Sends alerts via **Telegram Bot API** immediately when a value bet is detected.
* **Data Logging:** Automatically saves history to **Google Sheets** via API (`gspread`) for statistical analysis (ROI, EV).
* **Robustness:** Includes automatic error handling, exponential backoff retries, heartbeat monitoring, and MD5 hashing for unique event tracking.

## 🛠️ Tech Stack
* **Language:** Python 3.x
* **Web Scraping:** Playwright (Async), Aiohttp
* **APIs:** Telegram Bot API, Google Sheets API
* **Logic:** Asyncio for concurrency, JSON for local history.

## ⚙️ Installation & Usage

### 1. Clone the repository
```bash
git clone [https://github.com/LorSt4r/superquote-tracker.git](https://github.com/LorSt4r/superquote-tracker.git)
cd superquote-tracker

```

### 2. Install dependencies

First, install the required Python libraries:

```bash
pip install -r requirements.txt

```

Then, install the necessary browsers for Playwright (required for scraping):

```bash
playwright install

```

### 3. Configuration

Create a file named `.env` in the root directory. This file must contain your private keys and configuration settings.

**Example `.env` structure:**

```env
# Telegram Configuration
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
TELEGRAM_CHAT_IDS=12345678,87654321

# File Paths
SUPERQUOTE_HISTORY_FILE=superquote_history.json

# Google Sheets Configuration (Optional)
GOOGLE_SHEETS_CREDENTIALS_FILE=credentials.json
GOOGLE_SHEETS_SPREADSHEET_ID=your_google_sheet_id_here
GOOGLE_SHEETS_WORKSHEET_NAME=Database
HEALTHCHECK_URL=https://hc-ping.com/yourhealtcheckurl

```

*Note: You need to place your Google Service Account JSON file (renamed to `credentials.json`) in the project folder.*

### 4. Run the Bot

```bash
python superquote_checker.py

```

## ⚠️ Disclaimer

This project was created for **educational purposes only** to study statistical anomalies, web automation, and asynchronous programming. The author is not responsible for any financial losses or account limitations resulting from the use of this software.

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](https://www.google.com/search?q=LICENSE) file for details.

```

```
